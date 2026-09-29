"""Model-driven intelligence for Vyapaar Sahayak.

Hybrid design:
- ML predicts demand, opportunity potential and business risk.
- Deterministic financial rules remain safety guardrails.
- The LLM is used only to explain/communicate model outputs.

The bundled models are prototype models trained on transparent synthetic/scenario
examples. They are NOT trained on real rural-business records. The interfaces are
kept production-ready so labelled, anonymised outcomes can replace the prototype
training data later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


OPPORTUNITY_FEATURE_NAMES = [
    "rain_probability", "rain_mm_3d", "temperature",
    "festival_signal", "crop_signal", "consumer_signal",
    "nearby_activity_density", "nearby_relevant_density", "market_signal",
    "stock_days", "margin_pct", "cash_months", "receivables_pct", "emi_pct",
]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _opportunity_target(x: np.ndarray) -> float:
    (
        rain, rain_mm, temp, festival, crop, consumer,
        activity_density, relevant_density, market_signal,
        stock_days, margin, cash_months, rec_pct, emi_pct,
    ) = x
    score = (
        0.12 * festival + 0.10 * crop + 0.10 * consumer
        + 0.08 * _clip(rain / 100, 0, 1)
        + 0.06 * _clip(rain_mm / 30, 0, 1)
        + 0.06 * _clip((temp - 15) / 25, 0, 1)
        + 0.08 * _clip(activity_density / 80, 0, 1)
        + 0.10 * _clip(relevant_density / 35, 0, 1)
        + 0.08 * market_signal
        + 0.08 * _clip(margin / 50, 0, 1)
        + 0.08 * _clip(1 - abs(stock_days - 30) / 60, 0, 1)
        + 0.07 * _clip(cash_months / 3, 0, 1)
        + 0.06 * _clip(1 - rec_pct / 40, 0, 1)
        - 0.10 * _clip(emi_pct / 30, 0, 1)
    )
    return _clip(score, 0, 1)


@lru_cache(maxsize=1)
def _opportunity_model() -> RandomForestClassifier:
    rng = np.random.default_rng(42)
    rows, labels = [], []
    for _ in range(3200):
        x = np.array([
            rng.uniform(0, 100), rng.uniform(0, 40), rng.uniform(10, 45),
            rng.integers(0, 2), rng.integers(0, 2), rng.integers(0, 2),
            rng.uniform(0, 120), rng.uniform(0, 60), rng.integers(0, 2),
            rng.uniform(3, 120), rng.uniform(3, 55), rng.uniform(0.1, 6),
            rng.uniform(0, 60), rng.uniform(0, 35),
        ])
        score = _opportunity_target(x)
        label = int(score >= 0.46)
        if rng.random() < 0.035:
            label = 1 - label
        rows.append(x)
        labels.append(label)
    model = RandomForestClassifier(
        n_estimators=220, max_depth=9, min_samples_leaf=5,
        random_state=42, class_weight="balanced",
    )
    model.fit(np.asarray(rows), np.asarray(labels))
    return model


@lru_cache(maxsize=1)
def _risk_model() -> Pipeline:
    rng = np.random.default_rng(7)
    rows, targets = [], []
    for _ in range(2600):
        x = np.array([
            rng.uniform(-0.25, 0.45), rng.uniform(0.05, 8), rng.uniform(0, 0.7),
            rng.uniform(0, 1.2), rng.uniform(0, 0.5), rng.uniform(0, 2.5),
        ])
        margin, cash_m, rec, inv, emi, debt = x
        risk = 55 - margin * 55 - min(cash_m, 4) * 5 + rec * 35
        risk += max(inv - 0.25, 0) * 22 + emi * 55 + debt * 10
        risk += rng.normal(0, 3.5)
        rows.append(x)
        targets.append(_clip(risk, 0, 100))
    model = Pipeline([
        ("scale", StandardScaler()),
        ("model", RandomForestRegressor(
            n_estimators=180, max_depth=9, min_samples_leaf=6, random_state=7
        )),
    ])
    model.fit(np.asarray(rows), np.asarray(targets))
    return model


def _demand_features(history: list[float], idx: int, context: dict | None = None) -> list[float]:
    h = [float(v or 0) for v in history]
    lag1 = h[idx - 1]
    lag2 = h[idx - 2] if idx >= 2 else lag1
    start = max(0, idx - 3)
    rolling = float(np.mean(h[start:idx]))
    trend = lag1 - lag2
    context = context or {}
    month = int(context.get("month", 1))
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))
    rain = float(context.get("rain_probability", 0) or 0) / 100
    festival = float(context.get("festival_signal", 0) or 0)
    crop = float(context.get("crop_signal", 0) or 0)
    local_activity = float(context.get("nearby_relevant_density", 0) or 0) / 35
    return [lag1, lag2, rolling, trend, float(idx), month_sin, month_cos,
            rain, festival, crop, local_activity]


def _synthetic_demand_training() -> tuple[np.ndarray, np.ndarray]:
    """Create a pooled temporal prototype dataset with seasonal/local features."""
    rng = np.random.default_rng(2026)
    X, y = [], []
    for _ in range(260):
        base = rng.uniform(5, 80)
        trend = rng.uniform(-2.0, 4.0)
        history = []
        for month_idx in range(1, 13):
            seasonal = 1 + 0.14 * np.sin(2 * np.pi * month_idx / 12 + rng.uniform(-0.3, 0.3))
            festival = int(rng.random() < 0.18)
            crop = int(rng.random() < 0.20)
            rain = rng.uniform(0, 100)
            local_density = rng.uniform(0, 35)
            noise = rng.normal(0, max(1.0, base * 0.05))
            demand = max(0, base * seasonal + trend * month_idx + festival * base * 0.12
                         + crop * base * 0.08 + rain / 100 * base * 0.04
                         + local_density / 35 * base * 0.06 + noise)
            history.append(demand)
            if month_idx >= 4:
                features = _demand_features(history, month_idx, {
                    "month": month_idx,
                    "rain_probability": rain,
                    "festival_signal": festival,
                    "crop_signal": crop,
                    "nearby_relevant_density": local_density,
                })
                X.append(features)
                y.append(demand)
    return np.asarray(X), np.asarray(y)


@lru_cache(maxsize=1)
def _demand_model() -> RandomForestRegressor:
    X, y = _synthetic_demand_training()
    model = RandomForestRegressor(
        n_estimators=240, max_depth=10, min_samples_leaf=3, random_state=21,
    )
    model.fit(X, y)
    return model


def forecast_demand(history: Iterable[float], horizon: int = 1, context: dict | None = None) -> dict:
    """Forecast demand using a pooled contextual Random Forest.

    The model combines the shop's recent demand pattern with month/season,
    weather, crop/festival signals and nearby commercial activity. With fewer
    than 3 observations we deliberately use a conservative moving average.
    """
    history = [max(0.0, float(v or 0)) for v in history]
    if len(history) < 3:
        fallback = round(float(np.mean(history[-3:])) if history else 0.0, 1)
        return {"forecast": fallback, "method": "moving-average fallback", "stability": "Low"}

    context = context or {}
    next_month = int(context.get("month", 1))
    if len(history) >= 2:
        next_month = ((next_month - 1 + horizon) % 12) + 1
    model_context = {**context, "month": next_month}
    features = _demand_features(history, len(history), model_context)
    model = _demand_model()
    prediction = max(0.0, float(model.predict([features])[0]))
    spread = float(np.std([tree.predict([features])[0] for tree in model.estimators_]))
    stability = "Stable" if spread < max(1.0, prediction * 0.12) else "Variable"
    return {
        "forecast": round(prediction, 1),
        "method": "Contextual Random Forest demand model",
        "stability": stability,
        "model_spread": round(spread, 1),
        "context_used": [k for k in ("month", "rain_probability", "festival_signal", "crop_signal", "nearby_relevant_density") if k in context],
    }


def score_hyperlocal_opportunity(features: dict) -> dict:
    vector = np.array([[float(features.get(name, 0) or 0) for name in OPPORTUNITY_FEATURE_NAMES]])
    model = _opportunity_model()
    probability = float(model.predict_proba(vector)[0][1])
    return {
        "probability": round(probability * 100, 1),
        "label": "High potential" if probability >= 0.65 else "Moderate potential" if probability >= 0.45 else "Low potential",
        "model": "Random Forest hyper-local opportunity classifier",
        "training": "prototype scenario dataset",
        "features_used": OPPORTUNITY_FEATURE_NAMES,
    }


def score_business_risk(ratios: dict) -> dict:
    vector = [[
        ratios.get("operating_margin", 0), ratios.get("cash_position_ratio", 0),
        ratios.get("receivables_ratio", 0), ratios.get("inventory_to_revenue_ratio", 0),
        ratios.get("emi_burden_ratio", 0), ratios.get("debt_burden_ratio", 0),
    ]]
    risk = _clip(float(_risk_model().predict(vector)[0]), 0, 100)
    return {
        "risk_score": round(risk),
        "label": "High risk" if risk >= 65 else "Moderate risk" if risk >= 40 else "Lower risk",
        "model": "Random Forest business-risk model",
        "training": "prototype scenario dataset",
    }
