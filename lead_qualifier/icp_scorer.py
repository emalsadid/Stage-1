"""
Path2Ascension Lead Qualifier — ICP Scorer

Scores a normalised lead dict against the ICP_CRITERIA defined in config.py.
Returns a ScoreResult with the total score, max possible score, matched
criteria, and a pass/fail flag based on ICP_PASS_THRESHOLD.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from config import ICP_CRITERIA, ICP_PASS_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    score: int
    max_score: int
    passed: bool
    matched_criteria: list[str] = field(default_factory=list)
    missed_criteria: list[str] = field(default_factory=list)

    @property
    def score_pct(self) -> float:
        return round(self.score / self.max_score * 100, 1) if self.max_score else 0.0


def _normalise(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).lower().strip())


def _parse_employee_count(value: Any) -> Optional[int]:
    """
    Parse various employee count formats:
      "51-200", "51 - 200", "200", "1,500", "1500", "51 to 200"
    Returns the midpoint of a range, or the exact value.
    """
    text = _normalise(value).replace(",", "")
    if not text:
        return None

    # Range formats: "51-200", "51 to 200"
    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", text)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return (low + high) // 2

    # Single number
    num_match = re.search(r"(\d+)", text)
    if num_match:
        return int(num_match.group(1))

    return None


def _parse_revenue(value: Any) -> Optional[float]:
    """
    Parse revenue strings like "$5M", "$1.2M", "5000000", "1,200,000".
    Returns float in dollars.
    """
    text = _normalise(value).replace(",", "").replace("$", "")
    if not text:
        return None

    multipliers = {"b": 1e9, "m": 1e6, "k": 1e3}
    match = re.search(r"([\d.]+)\s*([bmk])?", text)
    if match:
        amount = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        return amount * multipliers.get(suffix, 1)

    return None


def _score_criterion(criterion: dict, lead: dict) -> tuple[bool, int]:
    """
    Evaluate a single criterion against a lead dict.
    Returns (matched: bool, weight: int).
    """
    field_name = criterion["field"]
    weight = criterion["weight"]
    match_type = criterion["match_type"]
    raw_value = lead.get(field_name, "")

    if match_type == "substring_any":
        normalised = _normalise(raw_value)
        if not normalised:
            return False, weight
        for term in criterion["matches"]:
            if _normalise(term) in normalised:
                return True, weight
        return False, weight

    elif match_type == "range":
        low, high = criterion["range"]
        if field_name == "employees":
            parsed = _parse_employee_count(raw_value)
        elif field_name == "annual_revenue":
            parsed = _parse_revenue(raw_value)
        else:
            try:
                parsed = float(str(raw_value).replace(",", ""))
            except (ValueError, TypeError):
                parsed = None

        if parsed is not None and low <= parsed <= high:
            return True, weight
        return False, weight

    else:
        logger.warning("Unknown match_type '%s' for criterion '%s'", match_type, criterion["name"])
        return False, weight


def score_lead(lead: dict) -> ScoreResult:
    """
    Score a normalised lead dict against all ICP_CRITERIA.

    Args:
        lead: Dict with internal field names (from config.APOLLO_FIELD_MAP values).

    Returns:
        ScoreResult with score, pass/fail, and breakdown.
    """
    total_score = 0
    max_score = sum(c["weight"] for c in ICP_CRITERIA)
    matched = []
    missed = []

    for criterion in ICP_CRITERIA:
        matched_flag, weight = _score_criterion(criterion, lead)
        if matched_flag:
            total_score += weight
            matched.append(criterion["name"])
        else:
            missed.append(criterion["name"])

    return ScoreResult(
        score=total_score,
        max_score=max_score,
        passed=total_score >= ICP_PASS_THRESHOLD,
        matched_criteria=matched,
        missed_criteria=missed,
    )
