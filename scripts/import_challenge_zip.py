"""Import the recruitment ZIP directly, without distributing the internal files."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import build_database
from app.policies import sections_from_pdf


def locate_inputs(archive: ZipFile) -> str:
    """Find the one internal policy PDF; product CSVs are located by the importer."""
    names = [name for name in archive.namelist() if name.lower().endswith(".pdf")]
    manuals = [name for name in names if "polit" in "".join(
        ch for ch in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(ch)
    ) or "pol#" in name.lower()]
    if len(manuals) != 1:
        raise ValueError("Expected exactly one store policy PDF inside the challenge ZIP")
    return manuals[0]


def import_zip(zip_path: Path, db_path: Path) -> dict:
    if not zip_path.is_file():
        raise FileNotFoundError(f"Challenge ZIP not found: {zip_path}")
    with ZipFile(zip_path) as archive, TemporaryDirectory(prefix="emporio_inputs_") as temp:
        destination = Path(temp)
        for entry in archive.infolist():
            # Untrusted archives must not overwrite files outside the temporary folder.
            components = Path(entry.filename.replace("\\", "/")).parts
            if entry.filename.startswith(("/", "\\")) or ".." in components:
                raise ValueError("Unsafe path inside challenge ZIP")
        manual = locate_inputs(archive)
        archive.extractall(destination)
        sections = sections_from_pdf(destination / manual)
        return build_database(db_path, destination, sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import private challenge materials for local use")
    parser.add_argument("zip", type=Path, help="Original ZIP provided with the assignment")
    parser.add_argument("--db", type=Path, default=Path("data/emporio.db"))
    args = parser.parse_args()
    counts = import_zip(args.zip, args.db)
    print("Imported:", ", ".join(f"{key}={count}" for key, count in counts.items()))
    print("Private local database:", args.db)


if __name__ == "__main__":
    main()
