"""Shared constants used across Vyapaar Sahayak."""

APP_NAME = "Vyapaar Sahayak"
APP_TAGLINE = "We don't just record business data. We turn business data into clear decisions."

BUSINESS_TYPES = [
    "Kirana Store",
    "Dairy Business",
    "Food Stall",
    "Tailoring",
    "Repair Shop",
    "Street Vendor",
    "Other",
]

LANGUAGES = ["English", "Hindi", "Punjabi"]

STATES = [
    "Punjab", "Haryana", "Uttar Pradesh", "Rajasthan", "Bihar", "Madhya Pradesh",
    "Gujarat", "Maharashtra", "Karnataka", "Tamil Nadu", "West Bengal", "Other",
]

SEASONS = ["Summer", "Monsoon", "Winter", "Festival", "Harvest", "Regular"]

EXPENSE_CATEGORIES = [
    "Inventory",
    "Supplier payments",
    "Rent / operating expenses",
    "Equipment",
    "Marketing",
    "Emergency cash buffer",
    "Other",
]

TIMEFRAMES = ["Today", "This Week", "This Month"]
ACTION_STATUSES = ["Not Started", "In Progress", "Completed"]

PRIORITY_ICON = {"High": "❤️", "Medium": "💛", "Low": "💚"}
PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

HEALTH_LABEL_COLORS = {
    "Healthy": "💚",
    "Needs Attention": "⁉️",
    "At Risk": "‼️",
    "Insufficient Data": "❓",
}

DEMO_PROFILE = {
    "name": "Rehan Ahmed",
    "business_type": "Tailoring",
    "location": "Kharar",
    "state": "Punjab",
    "district": "S.A.S Nagar",
    "language": "Hindi",
    "employees": 5,
}

DEMO_SNAPSHOT = {
    "revenue": 120000,
    "expenses": 55000,
    "inventory_value": 100000,
    "receivables": 32000,
    "cash": 70000,
    "loan_outstanding": 120000,
    "loan_emi": 6500,
}

DEMO_PREVIOUS_SNAPSHOT = {
    "revenue": 90000,
    "expenses": 50000,
    "inventory_value": 80000,
    "receivables": 37000,
    "cash": 58000,
    "loan_outstanding": 0,
    "loan_emi": 0,
}

DISCLAIMER = (
    "Vyapaar Sahayak is a prototype using simulated and self-reported data. "
    "It is not a lender, financial advisor, credit bureau, or government portal. "
    "All scores are illustrative indicators, not official credit scores. Verify scheme "
    "Eligibility and financing terms with official sources before acting."
)
