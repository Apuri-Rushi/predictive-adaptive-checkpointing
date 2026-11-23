"""
Read-only access to the Backblaze daily CSV files.

* The observation date is always the date in the FILE NAME (approved rule).
* The line terminator is sniffed per file, because 2019-06-17.csv uses CR-only endings.
* Only the requested columns are read, in chunks.
"""
import re
from pathlib import Path

import pandas as pd

from config import DATA_DIR

FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")


def daily_files(data_dir: Path = DATA_DIR):
    """Sorted list of (file_date, path) for every YYYY-MM-DD.csv file."""
    out = [(pd.Timestamp(FILE_RE.match(p.name).group(1)), p)
           for p in sorted(Path(data_dir).iterdir()) if FILE_RE.match(p.name)]
    if not out:
        raise FileNotFoundError(f"No daily CSV files in {data_dir}")
    return out


def line_terminator(path: Path):
    """None for LF/CRLF files (pandas default); '\\r' for CR-only files."""
    with open(path, "rb") as fh:
        head = fh.read(1 << 16)
    return "\r" if (b"\r" in head and b"\n" not in head) else None


def read_daily(path: Path, columns, chunksize: int = 200_000) -> pd.DataFrame:
    """Read selected columns of one daily file, chunk by chunk, as one small DataFrame
    (a single day is ~110k rows). SMART columns are parsed as float64.
    Columns are returned in the REQUESTED order (pandas `usecols` keeps file order)."""
    dtypes = {c: "float64" for c in columns if c.startswith("smart_")}
    dtypes.update({"serial_number": str, "model": str})
    parts = [ch for ch in pd.read_csv(path, usecols=columns, dtype=dtypes, chunksize=chunksize,
                                      lineterminator=line_terminator(path))]
    return pd.concat(parts, ignore_index=True)[list(columns)]
