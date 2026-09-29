"""
LLM abstraction layer.

Supports (in order of preference):
  1. Gemma 4 31B IT (via OpenRouter), if OPENROUTER_API_KEY is set.
  2. Google Gemini, if GEMINI_API_KEY is set.
  3. OpenAI, if OPENAI_API_KEY is set.
  4. Smart Demo Mode: the local explainable engine's own structured answer template.
     The ML models continue to run locally even when no LLM API is configured.

IMPORTANT RULE: the LLM is only ever asked to explain, prioritise,
simplify, and personalise numbers that the calculation engine already
computed. It is explicitly instructed never to invent financial figures.
The structured `context` dict is the single source of truth.

This module never raises: any API/network/library failure falls back
to Smart Demo Mode with a friendly message.
"""

import os
import json
import time

from services import recommendation_engine as rec_engine

SYSTEM_INSTRUCTIONS = """You are Vyapaar Sahayak, an AI business advisor for a rural or semi-urban Indian \
micro-entrepreneur (e.g. a kirana store, dairy business, food stall, tailor, or repair shop owner). \
You will be given a JSON object called BUSINESS_CONTEXT containing numbers already calculated by the \
application. You must NOT invent, guess, or alter any financial figures — only use the numbers given to \
you. Your job is only to explain, prioritise, simplify, and personalise recommendations in simple, warm, \
practical language a non-technical shop owner would understand.

Always structure your answer using exactly these section headings, in this order:
SHORT ANSWER
WHAT I NOTICED
WHAT YOU SHOULD DO
WHY
EXPECTED IMPACT

Rules:
- Never claim guaranteed profits or guaranteed outcomes.
- Never state or imply loan eligibility or approval.
- Use cautious language: "estimate", "may", "consider", "based on the information provided".
- Keep it concise: a few short bullet points per section, not long paragraphs.
- Do not give regulated financial, legal, or tax advice.
"""


def _build_prompt(context: dict, question: str, changes: list = None) -> str:
    payload = dict(context)
    if changes:
        payload["recent_changes"] = [c["text"] for c in changes]
    return (
        f"BUSINESS_CONTEXT:\n{json.dumps(payload, indent=2)}\n\n"
        f"OWNER'S QUESTION: {question if question.strip() else '(no specific question - give a general weekly check-in)'}"
    )


def _try_gemma(context: dict, question: str, changes: list = None):
    """Gemma 4 31B IT is an open-weight model - Google doesn't serve it directly through
    the Gemini API, so this goes through OpenRouter's OpenAI-compatible endpoint instead."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model="google/gemma-4-31b-it",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": _build_prompt(context, question, changes)},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def _try_gemini(context: dict, question: str, changes: list = None):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        from google.genai import errors as genai_errors
    except Exception:
        return None

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(context, question, changes)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTIONS,
                ),
            )
            text = (getattr(response, "text", "") or "").strip()
            return text or None
        except genai_errors.ServerError:
            # Transient (503 overloaded, etc.) - worth a short retry.
            if attempt < max_attempts:
                time.sleep(1.5 * attempt)  # 1.5s, then 3s
                continue
            return None
        except Exception:
            # Anything else (bad key, 404 model not found, quota, etc.)
            # is not going to be fixed by retrying - fail fast.
            return None
    return None


def _try_openai(context: dict, question: str, changes: list = None):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": _build_prompt(context, question, changes)},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def get_ai_response(context: dict, question: str, recommendations: list, changes: list = None) -> dict:
    """
    Returns {"mode": "gemma"|"gemini"|"openai"|"demo", "text": str, "note": str|None}
    Never raises.
    """
    text = _try_gemma(context, question, changes)
    if text:
        return {"mode": "gemma", "text": text, "note": None}

    text = _try_gemini(context, question, changes)
    if text:
        return {"mode": "gemini", "text": text, "note": None}

    text = _try_openai(context, question, changes)
    if text:
        return {"mode": "openai", "text": text, "note": None}

    demo_text = rec_engine.answer_format_template(context, recommendations, question, changes)
    have_key = bool(
        os.getenv("OPENROUTER_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    note = (
        "We couldn't connect to the AI service right now. Smart Demo Mode is still available."
        if have_key else
        "Running in Smart Demo Mode (no LLM API key configured). The local financial guardrails and "
        "ML models still run; this fallback only replaces the conversational LLM layer."
    )
    return {"mode": "demo", "text": demo_text, "note": note}