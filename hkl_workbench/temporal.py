"""Conservative interval queries; no parsing of free-text historical dates."""
from datetime import date, datetime


def active_assertions(assertions, as_of=None):
    """Correction changes the available assertion view, never the event history."""
    if as_of:
        datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    available = [a for a in assertions if as_of is None or a["recorded_at"] <= as_of]
    superseded = {a["supersedes"] for a in available if a["supersedes"]}
    return [a for a in available if a["ref"] not in superseded]


def time_match(period, day):
    date.fromisoformat(day)
    if period is None:
        return False
    if period["precision"] == "exact":
        return day == period["start"]
    # Normalized boundaries are query bounds, not asserted exact source dates.
    return (period["start"] is None or period["start"] <= day) and (period["end"] is None or day < period["end"])


def historical_location(profile, subject, day, as_of=None):
    candidates = [a for a in active_assertions(profile["assertions"], as_of) if a["subject"] == subject and a["predicate"] == "location" and time_match(a["time"], day)]
    locations = sorted({a["object"] for a in candidates})
    return {"subject": subject, "valid_at": day, "as_of": as_of,
            "status": "gap" if not locations else "overlap" if len(locations) > 1 else "supported",
            "locations": locations, "assertions": candidates}
