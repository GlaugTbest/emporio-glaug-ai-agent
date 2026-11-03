"""Import six challenge CSVs and locally extract policy PDF; no source is committed."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import build_database
from app.policies import sections_from_json, sections_from_pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("fixtures"),
                        help="Folder with six CSVs (recursive lookup)")
    parser.add_argument("--manual", type=Path, help="Original private policy PDF")
    parser.add_argument("--policy-json", type=Path,
                        help="Demo-only sanitized policy sections (instead of --manual)")
    parser.add_argument("--db", type=Path, default=Path("data/emporio.db"))
    args = parser.parse_args()
    if bool(args.manual) == bool(args.policy_json):
        parser.error("Pass exactly one: --manual original.pdf or --policy-json fixtures/demo_policies.json")
    sections = sections_from_pdf(args.manual) if args.manual else sections_from_json(args.policy_json)
    counts = build_database(args.db, args.source_dir, sections)
    print("Imported:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    print("Database ready:", args.db)


if __name__ == "__main__":
    main()
