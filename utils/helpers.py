"""Small formatting and safety helpers used across the app."""


def money(value) -> str:
    """Format a number as Indian-rupee currency, e.g. money(45000) -> '₹45,000'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "₹0"
    sign = "-" if value < 0 else ""
    return f"{sign}₹{abs(value):,.0f}"


def pct(value, decimals: int = 1) -> str:
    """Format a fraction (0.187) or a percentage-scale number as a percent string."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0%"
    return f"{value * 100:.{decimals}f}%"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_div(numerator, denominator, default: float = 0.0) -> float:
    """Division that never raises, and never returns inf/NaN."""
    try:
        numerator = float(numerator)
        denominator = float(denominator)
    except (TypeError, ValueError):
        return default
    if denominator == 0:
        return default
    result = numerator / denominator
    if result != result:  # NaN check
        return default
    return result


def clamp(value, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def first_name(full_name: str) -> str:
    if not full_name or not full_name.strip():
        return "there"
    return full_name.strip().split()[0]
