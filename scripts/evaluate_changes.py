#!/usr/bin/env python3
"""Freeze and score an offline evidence comparison. No network or provider calls."""
import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# Manually selected reference developments in the August migration snapshot.
# These are relevance checks, not verification that the published claims are true.
ARCHIVE_CASES = {
    "AO_HIGH_NORTH": (15, 7581, "Reported Finnish asylum decision involving a Russian family"),
    "AO_EUROPE": (20, 11049, "Reported exchange of deadly overnight strikes"),
    "AO_BALKANS": (21, 7862, "Security advice in Greece ahead of planned protests"),
    "AO_LEVANT": (17, 7633, "Reported approval of reconstruction inside Gaza's Yellow Line"),
}


def freeze_archive(archive):
    db = sqlite3.connect(f"{Path(archive).resolve().as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    cases = []
    try:
        for ao, (brief_id, reference_id, description) in ARCHIVE_CASES.items():
            brief = db.execute("SELECT * FROM briefs WHERE id = ? AND ao = ?", (brief_id, ao)).fetchone()
            if not brief:
                raise ValueError(f"Archive is missing brief {brief_id}")
            cutoff = datetime.fromisoformat(brief["generated_at"])
            evidence = [dict(row) for row in db.execute(
                """SELECT a.id, a.title, a.summary, a.published_at, a.cluster_key, s.name AS publisher
                   FROM articles a LEFT JOIN sources s ON s.id = a.source_id
                   WHERE a.ao = ? AND a.is_sigact = 1 AND a.published_at >= ? AND a.published_at < ?
                     AND (a.fetched_at IS NULL OR a.fetched_at <= ?)
                   ORDER BY a.id = ? DESC, a.severity DESC, a.published_at DESC, a.id DESC LIMIT 30""",
                (ao, str(cutoff - timedelta(hours=48)), str(cutoff), str(cutoff), reference_id),
            )]
            if not any(row["id"] == reference_id for row in evidence):
                raise ValueError(f"Archive evidence {reference_id} is missing at the cutoff")
            cases.append({
                "id": ao, "ao": ao, "cutoff_utc": cutoff.isoformat() + "Z", "evidence": evidence,
                "reference_developments": [{"id": "reference", "description": description, "supporting_ids": [reference_id]}],
                "baseline": {"brief_id": brief_id, "text": brief["content"]},
            })
    finally:
        db.close()
    cases.extend([
        {"id": "quiet", "evidence": [], "reference_developments": [], "baseline": None},
        {"id": "duplicates", "evidence": [
            {"id": 1, "title": "Agency announces a temporary closure", "publisher": "Agency", "cluster_key": "closure"},
            {"id": 2, "title": "Outlet repeats the agency announcement", "publisher": "Outlet", "cluster_key": "closure"},
        ], "reference_developments": [
            {"id": "closure", "description": "One announced closure; the second item repeats it", "supporting_ids": [1, 2]},
        ], "baseline": None},
    ])
    return {"cases": cases}


def score(case, reviewed_output):
    """Score reviewer-matched claims; prose and semantic support require human review."""
    evidence_ids = {article["id"] for article in case["evidence"]}
    references = {item["id"]: set(item["supporting_ids"]) for item in case["reference_developments"]}
    covered = set()
    supported = duplicates = unknown_citations = 0
    for item in reviewed_output["developments"]:
        key = item.get("reference_id")
        ids = set(item.get("article_ids", []))
        unknown_citations += len(ids - evidence_ids)
        if ids and ids <= evidence_ids and item.get("claims_supported") is True:
            supported += 1
            if key in references and ids & references[key]:
                duplicates += int(key in covered)
                covered.add(key)
    prose = reviewed_output.get("prose_score")
    if prose is not None and (type(prose) is not int or not 0 <= prose <= 4):
        raise ValueError("prose_score must be an integer from 0 to 4")
    return {
        "reference_developments_found": len(covered), "reference_developments_missed": sorted(references.keys() - covered),
        "supported_items": supported, "submitted_items": len(reviewed_output["developments"]),
        "duplicate_items": duplicates, "unknown_citations": unknown_citations, "prose_score": prose,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("archive")
    grade = commands.add_parser("score")
    grade.add_argument("dataset", type=Path)
    grade.add_argument("case_id")
    grade.add_argument("review", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze_archive(args.archive)
    else:
        cases = json.loads(args.dataset.read_text())["cases"]
        case = next((item for item in cases if item["id"] == args.case_id), None)
        if case is None:
            parser.error("unknown case ID")
        result = score(case, json.loads(args.review.read_text()))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
