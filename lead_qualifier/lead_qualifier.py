"""
Path2Ascension — Lead Qualifier CLI
====================================
Reads a raw lead CSV (Apollo, Instantly, Wellfound, or LinkedIn export),
applies the halal filter and ICP scorer, and outputs two CSVs:

  qualified_leads.csv   — passed both halal filter and ICP score
  rejected_leads.csv    — failed with reason and matched term logged

Usage:
  python lead_qualifier.py leads.csv
  python lead_qualifier.py leads.csv --source apollo
  python lead_qualifier.py leads.csv --source wellfound --no-scrape
  python lead_qualifier.py leads.csv --output-dir ./output
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from config import SOURCE_FIELD_MAPS, APOLLO_FIELD_MAP
from halal_filter import is_halal_lead
from icp_scorer import score_lead

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source auto-detection
# ---------------------------------------------------------------------------

def detect_source(headers: list[str]) -> str:
    """
    Guess the CSV source from its column headers.
    Returns one of: 'apollo', 'instantly', 'wellfound', 'linkedin'.
    Falls back to 'apollo' if uncertain.
    """
    header_set = {h.strip().lower() for h in headers}

    signatures = {
        "apollo":     {"seo description", "# employees", "latest funding"},
        "wellfound":  {"market", "team size", "angellist url"},
        "linkedin":   {"position", "url", "connected on"},
        "instantly":  {"campaign name", "subsequence", "email status"},
    }

    best_source = "apollo"
    best_count = 0
    for source, sig_fields in signatures.items():
        count = sum(1 for f in sig_fields if f in header_set)
        if count > best_count:
            best_count = count
            best_source = source

    return best_source


# ---------------------------------------------------------------------------
# Row normalisation
# ---------------------------------------------------------------------------

def normalise_row(row: dict, field_map: dict) -> dict:
    """
    Map raw CSV column names to internal field names.
    Columns not in the map are preserved under their original names.
    """
    normalised: dict = {}
    for raw_col, value in row.items():
        internal = field_map.get(raw_col.strip(), raw_col.strip().lower().replace(" ", "_"))
        normalised[internal] = value.strip() if isinstance(value, str) else value

    # Wellfound: split "Name" into first_name / last_name
    if "first_name" in normalised and " " in normalised.get("first_name", ""):
        parts = normalised["first_name"].split(None, 1)
        normalised["first_name"] = parts[0]
        normalised.setdefault("last_name", parts[1] if len(parts) > 1 else "")

    return normalised


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

QUALIFIED_EXTRA_FIELDS = ["icp_score", "icp_score_pct", "icp_matched", "icp_missed"]
REJECTED_EXTRA_FIELDS  = ["reject_reason", "reject_layer", "reject_term",
                           "icp_score", "icp_score_pct"]


def _write_csv(path: Path, rows: list[dict], extra_fields: list[str]) -> None:
    if not rows:
        logger.info("No rows to write for %s", path.name)
        return

    # Collect all keys preserving insertion order
    all_keys: list[str] = []
    seen: set = set()
    base_keys = [k for k in rows[0] if k not in extra_fields]
    for k in base_keys + extra_fields:
        if k not in seen:
            all_keys.append(k)
            seen.add(k)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d rows → %s", len(rows), path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_file(
    input_path: Path,
    output_dir: Path,
    source: Optional[str] = None,
    scrape_website: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        headers = reader.fieldnames or []

    if not raw_rows:
        logger.error("Input file is empty.")
        sys.exit(1)

    # Detect / select field map
    detected_source = source or detect_source(headers)
    field_map = SOURCE_FIELD_MAPS.get(detected_source, APOLLO_FIELD_MAP)
    logger.info("Source detected: %s (%d leads)", detected_source.upper(), len(raw_rows))

    qualified: list[dict] = []
    rejected:  list[dict] = []

    for i, raw_row in enumerate(raw_rows, start=1):
        lead = normalise_row(raw_row, field_map)

        # --- Halal filter ---
        halal_result = is_halal_lead(
            industry=lead.get("industry", ""),
            description=lead.get("seo_description", ""),
            website=lead.get("website", ""),
            scrape_website=scrape_website,
        )

        if not halal_result.is_halal:
            lead["reject_reason"] = "non_halal"
            lead["reject_layer"] = halal_result.layer
            lead["reject_term"]  = halal_result.matched_term
            lead["icp_score"]    = ""
            lead["icp_score_pct"] = ""
            rejected.append(lead)
            logger.debug(
                "[%d/%d] REJECTED (halal) %s — layer=%s term='%s'",
                i, len(raw_rows), lead.get("company", "?"),
                halal_result.layer, halal_result.matched_term,
            )
            continue

        # --- ICP scoring ---
        score_result = score_lead(lead)
        lead["icp_score"]    = score_result.score
        lead["icp_score_pct"] = f"{score_result.score_pct}%"

        if not score_result.passed:
            lead["reject_reason"] = "below_icp_threshold"
            lead["reject_layer"]  = "icp_scorer"
            lead["reject_term"]   = f"score={score_result.score}/{score_result.max_score}"
            rejected.append(lead)
            logger.debug(
                "[%d/%d] REJECTED (ICP) %s — score %d/%d missed=%s",
                i, len(raw_rows), lead.get("company", "?"),
                score_result.score, score_result.max_score,
                score_result.missed_criteria,
            )
            continue

        # --- Qualified ---
        lead["icp_matched"] = "|".join(score_result.matched_criteria)
        lead["icp_missed"]  = "|".join(score_result.missed_criteria)
        qualified.append(lead)
        logger.debug(
            "[%d/%d] QUALIFIED %s — score %d/%d",
            i, len(raw_rows), lead.get("company", "?"),
            score_result.score, score_result.max_score,
        )

        # Throttle scraping to be respectful
        if scrape_website and lead.get("website"):
            time.sleep(0.5)

    # Write outputs
    _write_csv(output_dir / "qualified_leads.csv", qualified, QUALIFIED_EXTRA_FIELDS)
    _write_csv(output_dir / "rejected_leads.csv",  rejected,  REJECTED_EXTRA_FIELDS)

    # Summary
    total = len(raw_rows)
    q = len(qualified)
    r = len(rejected)
    halal_rejects = sum(1 for row in rejected if row.get("reject_reason") == "non_halal")
    icp_rejects   = sum(1 for row in rejected if row.get("reject_reason") == "below_icp_threshold")

    print("\n" + "=" * 50)
    print(f"  Path2Ascension Lead Qualifier — Summary")
    print("=" * 50)
    print(f"  Total processed : {total}")
    print(f"  Qualified        : {q}  ({round(q/total*100, 1)}%)")
    print(f"  Rejected total   : {r}")
    print(f"    ↳ Non-halal    : {halal_rejects}")
    print(f"    ↳ Below ICP    : {icp_rejects}")
    print(f"  Output dir       : {output_dir.resolve()}")
    print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Path2Ascension Lead Qualifier — halal filter + ICP scoring",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the raw lead CSV file",
    )
    parser.add_argument(
        "--source",
        choices=["apollo", "instantly", "wellfound", "linkedin"],
        default=None,
        help="Force a specific CSV source format (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write qualified_leads.csv and rejected_leads.csv (default: ./output)",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip website scraping (Layer 2b). Faster but less thorough.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-lead debug output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.input.exists():
        logger.error("File not found: %s", args.input)
        sys.exit(1)

    process_file(
        input_path=args.input,
        output_dir=args.output_dir,
        source=args.source,
        scrape_website=not args.no_scrape,
    )


if __name__ == "__main__":
    main()
