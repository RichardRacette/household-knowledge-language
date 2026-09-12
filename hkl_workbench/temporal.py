"""Conservative interval queries; no parsing of free-text historical dates."""
from datetime import date, datetime


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def active_assertions(assertions, as_of=None):
    """Correction changes the available assertion view, never the event history."""
    if as_of:
        timestamp(as_of)
    available = [a for a in assertions if as_of is None or timestamp(a["recorded_at"]) <= timestamp(as_of)]
    superseded = {a["supersedes"] for a in available if a["supersedes"]}
    return [a for a in available if a["ref"] not in superseded]


def source_recording_times(profile):
    """Earliest supporting assertion; source capture date is not availability.

    Standalone source-ingest timestamps are absent from profile 1.0. Sources with
    no recorded assertion have unknown availability and are excluded as of a time.
    """
    times = {}
    for a in profile["assertions"]:
        for ref in a["source_refs"]:
            if ref not in times or timestamp(a["recorded_at"]) < timestamp(times[ref]):
                times[ref] = a["recorded_at"]
    return times


def available_as_of(profile, as_of):
    times = source_recording_times(profile)
    return {"as_of": as_of, "assertions": [a["ref"] for a in active_assertions(profile["assertions"], as_of)],
            "evidence": sorted(r for r, t in times.items() if timestamp(t) <= timestamp(as_of)),
            "source_time_basis": "earliest recorded supporting assertion; unreferenced source availability unknown"}


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
