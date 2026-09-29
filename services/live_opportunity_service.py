"""
Hyper-local business intelligence with live signals and safe fallback.

Live signal: Open-Meteo geocoding + weather forecast (no API key required).
Hyper-local context: curated crop-cycle, festival/wedding and consumer-pattern data.
Fallback: if live weather/geocoding is unavailable, the curated local intelligence
is still returned, and get_hyperlocal_opportunities() explains why via "live_error".
"""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from services import ai_engine

BASE = Path(__file__).resolve().parent.parent
SIGNALS_PATH = BASE / "data" / "hyperlocal_signals.json"


# ============================================================
# LOW-LEVEL HELPERS
# ============================================================

def _get_json(url: str, timeout: int = 8) -> dict:
    req = Request(url, headers={"User-Agent": "VyapaarSahayakAI/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_signals() -> dict:
    if not SIGNALS_PATH.exists():
        return {}
    with SIGNALS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _geocode_search(query: str) -> list[dict]:
    """One Open-Meteo geocoding call, restricted to India. Never raises."""
    url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={quote(query)}&count=10&language=en&format=json&countryCode=IN"
    )
    try:
        return _get_json(url).get("results") or []
    except Exception:
        return []


def _geocode(location: str, state: str = "", district: str = "") -> dict | None:
    """
    Geocode a location as precisely as possible.

    Priority: exact name + exact state -> exact name anywhere in India ->
    name-starts-with in the same state -> first Indian result -> district
    fallback. countryCode=IN is enforced throughout so a same-named place
    abroad is never picked.
    """
    if not location or not location.strip():
        return None
    location = location.strip()
    state = (state or "").strip()
    district = (district or "").strip()

    results = _geocode_search(f"{location}, {state}") if state else []
    if not results:
        results = _geocode_search(location)

    if results:
        loc_l, state_l = location.lower(), state.lower()
        for r in results:
            if (r.get("name", "").strip().lower() == loc_l and r.get("country_code") == "IN"
                    and (not state_l or r.get("admin1", "").strip().lower() == state_l)):
                return r
        for r in results:
            if r.get("name", "").strip().lower() == loc_l and r.get("country_code") == "IN":
                return r
        for r in results:
            if (r.get("name", "").strip().lower().startswith(loc_l)
                    and (not state_l or r.get("admin1", "").strip().lower() == state_l)):
                return r
        for r in results:
            if r.get("country_code") == "IN":
                return r

    if district:
        d_results = _geocode_search(f"{district}, {state}" if state else district)
        for r in d_results:
            if r.get("country_code") == "IN" and (not state or r.get("admin1", "").lower() == state.lower()):
                return r
        if d_results:
            return d_results[0]

    return None


@lru_cache(maxsize=128)
def _nearby_osm_context(latitude: float, longitude: float, business_type: str = "") -> dict:
    """Fetch real nearby commercial/community signals from OpenStreetMap.

    This is deliberately a *context* signal, not a claim of consumer demand.
    OSM data is community-maintained and may be incomplete. If unavailable,
    the rest of the hyper-local engine continues using weather + curated data.
    """
    query = f"""
    [out:json][timeout:10];
    (
      nwr(around:5000,{latitude},{longitude})[shop];
      nwr(around:5000,{latitude},{longitude})[amenity=marketplace];
      nwr(around:5000,{latitude},{longitude})[amenity=restaurant];
      nwr(around:5000,{latitude},{longitude})[amenity=cafe];
      nwr(around:5000,{latitude},{longitude})[amenity=school];
      nwr(around:5000,{latitude},{longitude})[amenity=hospital];
      nwr(around:5000,{latitude},{longitude})[tourism=attraction];
      nwr(around:5000,{latitude},{longitude})[leisure=stadium];
    );
    out center tags;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        req = Request(url, data=query.encode("utf-8"), headers={"User-Agent": "VyapaarSahayakAI/1.0"}, method="POST")
        with urlopen(req, timeout=14) as response:
            data = json.loads(response.read().decode("utf-8"))
        elements = data.get("elements", [])
    except Exception as exc:
        return {"available": False, "error": str(exc), "count": 0, "relevant_count": 0, "market_count": 0}

    business = (business_type or "").lower()
    relevant_terms = {
        "tailor": ("tailor", "clothes", "fabric", "fashion", "sewing"),
        "kirana": ("supermarket", "convenience", "grocery", "general"),
        "food": ("restaurant", "cafe", "bakery", "fast_food", "food"),
        "street": ("marketplace", "restaurant", "cafe", "shop"),
    }
    terms = next((v for k, v in relevant_terms.items() if k in business),
                 ("shop", "market", "store", "retail"))
    relevant = 0
    markets = 0
    nearest_market_m = None
    for el in elements:
        tags = el.get("tags", {}) or {}
        blob = " ".join(str(v).lower() for v in tags.values())
        if any(t in blob for t in terms):
            relevant += 1
        if tags.get("amenity") == "marketplace" or "market" in blob:
            markets += 1
            center = el.get("center") or {}
            lat2, lon2 = center.get("lat", el.get("lat")), center.get("lon", el.get("lon"))
            if lat2 is not None and lon2 is not None:
                # Approximate distance in metres; sufficient for UI context.
                from math import asin, cos, radians, sin, sqrt
                R = 6371000
                p1, p2 = radians(latitude), radians(float(lat2))
                dp = radians(float(lat2) - latitude)
                dl = radians(float(lon2) - longitude)
                a = sin(dp/2)**2 + cos(p1) * cos(p2) * sin(dl/2)**2
                distance = 2 * R * asin(sqrt(a))
                nearest_market_m = distance if nearest_market_m is None else min(nearest_market_m, distance)

    area_km2 = 3.14159 * 5 * 5
    return {
        "available": True,
        "source": "OpenStreetMap / Overpass",
        "radius_km": 5,
        "count": len(elements),
        "relevant_count": relevant,
        "market_count": markets,
        "density_per_km2": round(len(elements) / area_km2, 1),
        "relevant_density_per_km2": round(relevant / area_km2, 1),
        "nearest_market_km": round(nearest_market_m / 1000, 2) if nearest_market_m is not None else None,
    }


def _weather(latitude: float, longitude: float) -> dict:
    """Current conditions + 3-day forecast from Open-Meteo."""
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,precipitation,rain,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,precipitation_probability_max,precipitation_sum"
        "&forecast_days=3&timezone=auto"
    )
    data = _get_json(url)
    if not data:
        raise ValueError("Weather service returned no data.")
    return data


def _weather_text(code: int | None) -> str:
    if code is None:
        return "Current weather conditions"
    if code in (0, 1):
        return "Clear or mostly clear"
    if code in (2, 3):
        return "Partly cloudy or overcast"
    if code in (45, 48):
        return "Foggy"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain showers"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Changing weather"


def _matching_hyperlocal(state: str, business_type: str, month: int) -> list[dict]:
    """Curated crop-cycle / festival / consumer-trend signals for this state and month.
    Falls back to a generic "Default" dataset if the state isn't in the curated file
    (e.g. "Other" was selected, or a state we haven't hand-curated yet), so this never
    silently returns nothing just because of an uncovered state."""
    signals_data = _load_signals()
    state_data = signals_data.get(state) or signals_data.get("Default") or {}
    if not state_data:
        return []

    matches = []
    for item in state_data.get("crop_cycles", []):
        if month in item.get("months", []):
            matches.append({"type": "Agricultural cycle", **item})

    for item in state_data.get("festivals", []):
        if month in item.get("months", []) and (not item.get("business_types") or business_type in item["business_types"]):
            matches.append({"type": "Regional festival / wedding window", **item})

    for item in state_data.get("consumer_trends", []):
        if not item.get("business_types") or business_type in item["business_types"]:
            matches.append({"type": "Neighbouring consumer trend", **item})

    return matches


def _weather_suggestions(business_type: str, daily: dict) -> list[str]:
    business = (business_type or "").lower()
    rain_probability = max(daily.get("precipitation_probability_max") or [0])
    rain_sum = sum(daily.get("precipitation_sum") or [])
    max_temperature = max(daily.get("temperature_2m_max") or [0])
    is_tailor = "tailor" in business or "clothing" in business

    suggestions = []
    if rain_probability >= 60 or rain_sum >= 5:
        if is_tailor:
            suggestions.append(
                "Local weather signal: rain is likely. Highlight alteration/repair "
                "services and plan customer pickup timelines."
            )
        else:
            suggestions.append(
                "Local weather signal: rain is likely. Review weather-sensitive "
                "stock and delivery plans."
            )
    if max_temperature >= 35 and is_tailor:
        suggestions.append(
            "Warm-weather signal: consider highlighting lightweight cotton "
            "fabrics and comfortable stitching options."
        )
    return suggestions


# ============================================================
# MAIN HYPER-LOCAL ENGINE
# ============================================================

def get_hyperlocal_opportunities(
    location: str, state: str, district: str, business_type: str,
    season: str = "Regular", local_event: str = "", snapshot: dict | None = None, inventory: list | None = None,
) -> dict:
    """Live weather + curated local intelligence + an AI-style business analysis."""
    now = datetime.now().astimezone()
    state_name = (state or "Punjab").strip()
    business_name = (business_type or "Any").strip()
    location_name = (location or "").strip()
    district_name = (district or "").strip()

    matches = _matching_hyperlocal(state_name, business_name, now.month)
    if local_event and local_event.strip():
        matches.insert(0, {
            "type": "User-provided local event",
            "signal": local_event.strip(),
            "implication": "Consider preparing relevant stock or service capacity before the event.",
        })

    live_error = None
    place, weather = None, None
    try:
        place = _geocode(location_name, state_name, district_name)
        if not place:
            raise ValueError(
                f"Could not find location '{location_name}'. Try entering a city or "
                "town name such as Ludhiana, Chandigarh or Amritsar."
            )
        weather = _weather(float(place["latitude"]), float(place["longitude"]))
    except Exception as exc:
        live_error = str(exc)

    if weather and place:
        current, daily = weather.get("current", {}), weather.get("daily", {})
        weather_suggestions = _weather_suggestions(business_name, daily)
        mode = "LIVE + CURATED"
        source = "Open-Meteo + OpenStreetMap + Vyapaar Sahayak local intelligence dataset"
        weather_block = {
            "location_name": place.get("name", location_name),
            "admin1": place.get("admin1", state_name),
            "country": place.get("country", "India"),
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "temperature": current.get("temperature_2m"),
            "temperature_unit": weather.get("current_units", {}).get("temperature_2m", "°C"),
            "rain_probability": max(daily.get("precipitation_probability_max") or [0]),
            "three_day_rain_mm": round(sum(daily.get("precipitation_sum") or []), 1),
            "wind": current.get("wind_speed_10m"),
            "wind_unit": weather.get("current_units", {}).get("wind_speed_10m", "km/h"),
            "weather": _weather_text(current.get("weather_code")),
        }
    else:
        mode = "CURATED FALLBACK"
        source = "Vyapaar Sahayak local intelligence dataset"
        weather_suggestions, weather_block = [], None

    nearby_context = _nearby_osm_context(float(place["latitude"]), float(place["longitude"]), business_name) if place else {"available": False, "error": "Location unavailable"}
    if nearby_context.get("available"):
        nearby_implication = (
            f"Within a 5 km radius, OpenStreetMap currently lists {nearby_context.get("count", 0)} mapped local places, "
            f"including about {nearby_context.get("relevant_count", 0)} relevant to this business type. "
            "This is a local-activity proxy, not a direct measure of demand."
        )
        matches.insert(0, {
            "type": "Live nearby activity",
            "signal": "5 km commercial/community context",
            "implication": nearby_implication,
            "source": "OpenStreetMap / Overpass",
        })

    suggestions = weather_suggestions + [m["implication"] for m in matches[:3] if m.get("implication")]
    if not suggestions:
        suggestions = ["No strong local signal matched right now. Review sales and inventory trends before making a large purchase."]

    signal_types = {str(m.get("type", "")).lower() for m in matches}
    weather_for_model = weather_block or {}
    model_features = {
        "rain_probability": weather_for_model.get("rain_probability", 0),
        "rain_mm_3d": weather_for_model.get("three_day_rain_mm", 0),
        "temperature": weather_for_model.get("temperature", 25),
        "festival_signal": 1 if any("festival" in t or "wedding" in t for t in signal_types) else 0,
        "crop_signal": 1 if any("agricultural" in t or "crop" in t for t in signal_types) else 0,
        "consumer_signal": 1 if any("consumer" in t for t in signal_types) else 0,
        "nearby_activity_density": nearby_context.get("density_per_km2", 0) if nearby_context.get("available") else 0,
        "nearby_relevant_density": nearby_context.get("relevant_density_per_km2", 0) if nearby_context.get("available") else 0,
        "market_signal": 1 if nearby_context.get("market_count", 0) > 0 else 0,
        "stock_days": (
            sum(float(i.get("quantity", 0) or 0) for i in (inventory or []))
            / max(1.0, sum(float(i.get("monthly_units_sold", 0) or 0) for i in (inventory or []))) * 30
            if inventory else 30
        ),
        "margin_pct": (
            sum((float(i.get("selling_price", 0) or 0) - float(i.get("purchase_price", 0) or 0))
                / max(1.0, float(i.get("selling_price", 0) or 0)) * 100 for i in (inventory or []))
            / max(1, len(inventory or []))
            if inventory else 20
        ),
        "cash_months": (
            float((snapshot or {}).get("cash", 0) or 0)
            / max(1.0, float((snapshot or {}).get("expenses", 0) or 0))
            if snapshot else 1.5
        ),
        "receivables_pct": (
            float((snapshot or {}).get("receivables", 0) or 0)
            / max(1.0, float((snapshot or {}).get("revenue", 0) or 0)) * 100
            if snapshot else 10
        ),
        "emi_pct": (
            float((snapshot or {}).get("loan_emi", 0) or 0)
            / max(1.0, float((snapshot or {}).get("revenue", 0) or 0)) * 100
            if snapshot else 10
        ),
    }
    ml_opportunity = ai_engine.score_hyperlocal_opportunity(model_features)

    # Connect the ML demand signal to the actual catalogue.
    item_actions = []
    for item in (inventory or []):
        history = item.get("history") or []
        units = float(item.get("monthly_units_sold", 0) or 0)
        if not history and units <= 0:
            continue
        item_context = {
            "month": now.month,
            "rain_probability": weather_block.get("rain_probability", 0) if weather_block else 0,
            "festival_signal": model_features["festival_signal"],
            "crop_signal": model_features["crop_signal"],
            "nearby_relevant_density": model_features["nearby_relevant_density"],
        }
        forecast = ai_engine.forecast_demand(history or [units, units, units], context=item_context)["forecast"]
        qty = float(item.get("quantity", 0) or 0)
        if forecast > max(1, qty) and forecast > max(1, units) * 1.08:
            gap = max(0, forecast - qty)
            cost = gap * float(item.get("purchase_price", 0) or 0)
            item_actions.append({
                "product": item.get("product_name", "Product"),
                "forecast": round(forecast, 1),
                "current_stock": round(qty, 1),
                "gap": round(gap, 1),
                "estimated_cost": round(cost, 2),
                "reason": [
                    f"ML forecast is {forecast:.1f} units versus {qty:.1f} currently in stock",
                    "local signal is active" if (model_features["festival_signal"] or model_features["crop_signal"] or model_features["consumer_signal"]) else "recent demand pattern supports the increase",
                    f"nearby relevant activity density: {model_features["nearby_relevant_density"]:.1f}/km²" if nearby_context.get("available") else "nearby activity data unavailable",
                ],
            })
    item_actions.sort(key=lambda x: x["gap"] * max(1, x["estimated_cost"]), reverse=True)

    analysis = generate_business_analysis(
        location=location_name, state=state_name, district=district_name,
        business_type=business_name, season=season, local_event=local_event,
        signals=matches[:5], weather=weather_block,
    )

    return {
        "mode": mode,
        "source": source,
        "updated_at": now.strftime("%d %b %Y, %I:%M %p"),
        "weather": weather_block,
        "signals": matches[:5],
        "suggestions": suggestions[:5],
        "analysis": analysis,
        "ml_opportunity": ml_opportunity,
        "model_features": model_features,
        "nearby_context": nearby_context,
        "inventory_actions": item_actions[:5],
        "live_error": live_error,
    }


def get_live_opportunities(location: str, state: str, district: str, business_type: str) -> dict:
    """Backward-compatible wrapper: raises if live weather is unavailable (older page code)."""
    result = get_hyperlocal_opportunities(location=location, state=state, district=district, business_type=business_type)
    if not result["weather"]:
        raise ValueError(result.get("live_error") or "Live weather unavailable")
    w = result["weather"]
    return {
        "source": result["source"], "location_name": w["location_name"], "admin1": w["admin1"],
        "temperature": w["temperature"], "temperature_unit": w["temperature_unit"],
        "rain_probability": w["rain_probability"], "three_day_rain_mm": w["three_day_rain_mm"],
        "wind": w["wind"], "wind_unit": w["wind_unit"], "weather": w["weather"],
        "updated_at": result["updated_at"], "suggestions": result["suggestions"],
    }


# ============================================================
# AI-STYLE BUSINESS ANALYSIS (rule-based, explainable - no LLM call here)
# ============================================================

def _festival_analysis(festival_name: str, business_type: str, business: str, location: str):
    """Returns (analysis, actions, opportunities, timing, risks) for ANY matched festival
    or wedding-window signal - not hardcoded to one festival. The same three business-type
    branches (tailoring/clothing, grocery/kirana, general) that used to be special-cased for
    Dussehra now apply to whatever festival the local signals (or the user) actually named."""
    opportunities = [
        f"Festive demand can create a short-term increase in customer activity around "
        f"{festival_name}, especially for clothing preparation, alterations and last-minute orders."
    ]
    timing = [
        f"Begin advance-order promotion around 10-14 days before {festival_name} and reserve "
        "additional capacity during the final 3-5 days."
    ]

    if "tailor" in business or "clothing" in business or "garment" in business:
        analysis = [
            f"For a {business_type} business in {location}, {festival_name} should be treated "
            "primarily as a time-sensitive service-demand opportunity rather than a "
            "reason to make a large inventory purchase.",
            "Customers may require garments to be stitched, fitted or altered before "
            "family gatherings, religious visits and festive events.",
        ]
        actions = [
            "Reserve daily stitching capacity for urgent festive orders.",
            "Promote alteration and fitting services because they have shorter "
            "turnaround times than completely new garments.",
            "Keep commonly used threads, zippers, buttons, hooks, lining and other "
            "small tailoring materials available.",
            "Contact repeat customers and offer advance booking slots before the final week.",
            "Create a clearly communicated express-order option with a realistic delivery time.",
        ]
        opportunities = [
            "Blouse and kurta fitting", "Pant and sleeve alterations", "Zip/button replacement",
            "Minor garment repairs", "Express festive stitching", "Advance booking for family orders",
        ]
        risks = [
            "Do not significantly increase finished-garment inventory unless previous "
            "sales data supports the decision.",
            "Avoid accepting more urgent orders than the shop can complete before the promised delivery date.",
            "Festive demand is time-sensitive, so late preparation can result in missed "
            "orders rather than delayed demand.",
        ]
    elif "grocery" in business or "kirana" in business:
        analysis = [
            f"For a {business_type} business in {location}, {festival_name} can increase demand "
            "for festival-related groceries, snacks, beverages and household items."
        ]
        actions = [
            "Review sales history from the previous festive period.",
            "Increase stock gradually instead of making one large purchase.",
            "Prioritize fast-moving products with proven local demand.",
            "Monitor nearby shops and local event activity for demand changes.",
            "Keep additional working capital available for fast replenishment.",
        ]
        opportunities = [
            "Festival snacks", "Beverages", "Cooking ingredients",
            "Household consumables", "Small festive-use products",
        ]
        risks = [
            "Avoid overstocking products with short shelf lives.",
            "Do not assume national festival demand automatically reflects demand in the local market.",
        ]
    else:
        analysis = [
            f"For a {business_type} business in {location}, {festival_name} represents a "
            "potential temporary increase in local customer activity."
        ]
        actions = [
            "Identify products or services historically associated with the festival period.",
            "Compare current inventory with previous festive sales.",
            "Prepare additional capacity only where local demand evidence supports it.",
            "Use advance bookings or customer communication to reduce uncertainty.",
        ]
        risks = [
            "Do not treat the festival signal as a guaranteed sales forecast. "
            "Validate the opportunity against your own historical sales."
        ]

    return analysis, actions, opportunities, timing, risks


def _top_festival_signal(local_event: str, signals: list[dict]) -> str | None:
    """The festival/wedding-window name to reason about: whatever the user explicitly
    typed takes priority, otherwise the strongest matched curated festival signal."""
    if local_event and local_event.strip():
        return local_event.strip()
    for signal in signals:
        if signal.get("type") in ("Regional festival / wedding window", "User-provided local event"):
            name = signal.get("signal", "").strip()
            if name:
                return name
    return None


def generate_business_analysis(
    location: str, state: str, district: str, business_type: str,
    season: str, local_event: str, signals: list[dict], weather: dict | None,
) -> dict:
    """Rule-based 'AI Business Analysis' block: summary, analysis, opportunities,
    recommended actions, timing and risks - built from the same signals the rest
    of the page shows, never from invented numbers."""
    location = location or "local area"
    business_type = business_type or "local business"
    business = business_type.lower()

    analysis, actions, timing, opportunities, risks = [], [], [], [], []

    festival_name = _top_festival_signal(local_event, signals)
    if festival_name:
        analysis, actions, opportunities, timing, risks = _festival_analysis(festival_name, business_type, business, location)

    if weather:
        rain_probability = weather.get("rain_probability", 0)
        rain_mm = weather.get("three_day_rain_mm", 0)
        temperature = weather.get("temperature")

        if rain_probability >= 60 or rain_mm >= 5:
            analysis.append(
                f"The live weather signal shows a relatively high rain possibility "
                f"({rain_probability}% over the forecast window). This can affect "
                "customer visits, pickup timelines and delivery planning."
            )
            actions.append(
                "Keep pickup and delivery commitments realistic and consider "
                "contacting customers in advance if weather may affect collection."
            )
            risks.append(
                "Weather forecasts can change, so use the weather signal for "
                "short-term planning rather than long-term purchasing."
            )
        if temperature is not None:
            analysis.append(
                f"The current reported temperature is approximately "
                f"{temperature} {weather.get('temperature_unit', '°C')}."
            )

    for signal in signals[:5]:
        signal_name = signal.get("signal", "")
        if signal_name and signal_name.strip() != festival_name:  # avoid repeating what _festival_analysis already covered
            analysis.append(
                f"{signal.get('type', 'Local signal')}: {signal_name}. This signal "
                "should be considered together with the business's own sales history "
                "rather than used as a standalone demand forecast."
            )

    actions.append("Compare the recommendation with the shop's recent sales before committing significant working capital.")
    actions.append("Prefer small, reversible inventory or capacity adjustments when the signal is uncertain.")

    if not analysis:
        analysis.append(
            f"No strong event-specific pattern was identified for {business_type} in "
            f"{location}. The available signals should be treated as supporting "
            "information rather than a direct sales prediction."
        )
    if not opportunities:
        opportunities.append("Use the local signal to investigate potential short-term customer demand.")
    if not timing:
        timing.append("Monitor the signal over the next several days and compare it with recent sales before increasing stock or capacity.")
    if not risks:
        risks.append("Local intelligence indicates an opportunity, not a guaranteed sales increase.")

    return {
        "summary": (
            f"Based on the available local signals for {location}, {business_type} "
            "businesses should use this information for short-term planning rather "
            "than treating it as a guaranteed sales forecast."
        ),
        "analysis": analysis,
        "opportunities": opportunities,
        "recommended_actions": actions,
        "timing": timing,
        "risks": risks,
    }