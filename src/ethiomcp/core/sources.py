"""Helpers for fetching external repositories and reading common data formats."""

from __future__ import annotations

import csv
import shutil
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .connector import ConnectorError


@dataclass
class GitSource:
    """A git repository that is shallow-cloned on the first setup and pulled after that."""

    url: str
    ref: str | None = None

    def ensure(
        self, dest: Path, *, force: bool = False, log: Callable[[str], None] = print
    ) -> Path:
        git = shutil.which("git")
        if not git:
            raise ConnectorError("git is required to fetch " + self.url)
        if force and dest.exists():
            shutil.rmtree(dest)
        if (dest / ".git").exists():
            log(f"Updating {self.url} in {dest}")
            subprocess.run([git, "-C", str(dest), "pull", "--ff-only", "--depth", "1"], check=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            log(f"Cloning {self.url} into {dest}")
            cmd = [git, "clone", "--depth", "1"]
            if self.ref:
                cmd += ["--branch", self.ref]
            subprocess.run([*cmd, self.url, str(dest)], check=True)
        return dest


def safe_join(root: Path, relative: str) -> Path:
    """Join ``relative`` to ``root``, and refuse paths that point outside ``root``."""
    root = root.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ConnectorError(f"path outside the repository: {relative}")
    return target


def read_tsv(path: Path, *, comment: str | None = "#") -> Iterator[list[str]]:
    """Read the rows of a tab-separated file, skipping blank lines and comments."""
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if not row or not any(cell.strip() for cell in row):
                continue
            if comment and row[0].lstrip().startswith(comment):
                continue
            yield [cell.strip() for cell in row]


def read_xlsx(path: Path, sheet: str | None = None) -> Iterator[list[str]]:
    """Read the rows of an .xlsx sheet as strings, using openpyxl in read-only mode."""
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.worksheets[0]
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v).strip() for v in row]
            if any(cells):
                yield cells
    finally:
        wb.close()
