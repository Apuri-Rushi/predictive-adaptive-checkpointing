#!/usr/bin/env python
"""
Provenance and spreadsheet-conversion check for the Backblaze Q2 2019 daily CSVs (read-only).

1. Compares every local daily CSV against its member in the downloaded archive
   (size + CRC32 from the ZIP directory, plus SHA-256 of both copies for any file
   flagged by the audit).
2. For each file, detects spreadsheet-conversion markers: non-CRLF/LF line endings,
   non-ISO dates and scientific-notation numeric tokens. For flagged files it
   counts the scientific-notation cells per column.

Nothing is extracted into the dataset folder and nothing is modified. When the
archive copy of a file is needed for hashing, it is streamed in memory.

Usage (from C:/Users/rushi/CC_project):
    python -I project/ml/preprocessing/verify_provenance.py \
        --data project/dataset/backblaze_q2_2019 --zip data_Q2_2019.zip \
        --out project/ml/results/dataset_audit_revalidation
"""
import argparse
import hashlib
import os
import re
import zipfile
import zlib
from collections import Counter

import pandas as pd

SCI = re.compile(r"^-?\d+(\.\d+)?E[+-]\d+$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def crc32_file(path):
    c = 0
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 24), b""):
            c = zlib.crc32(blk, c)
    return c & 0xFFFFFFFF


def sha256_stream(fh):
    h = hashlib.sha256()
    for blk in iter(lambda: fh.read(1 << 20), b""):
        h.update(blk)
    return h.hexdigest()


def conversion_markers(path):
    """Line terminator, non-ISO date rows and per-column scientific-notation counts."""
    with open(path, "rb") as fh:
        head = fh.read(1 << 16)
    term = "CRLF" if b"\r\n" in head else "LF" if b"\n" in head else "CR-only" if b"\r" in head else "unknown"
    lt = "\r" if term == "CR-only" else None
    sci_cols, non_iso = Counter(), 0
    # Read everything as text so values are inspected exactly as written in the file.
    for ch in pd.read_csv(path, dtype=str, chunksize=50_000, lineterminator=lt, keep_default_na=False):
        non_iso += int((~ch["date"].str.match(ISO)).sum())
        for c in ch.columns[5:]:
            n = int(ch[c].str.contains("E+", regex=False).sum())
            if n:
                sci_cols[c] += int(ch[c].str.match(SCI).sum())
    return term, non_iso, sci_cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="project/dataset/backblaze_q2_2019")
    ap.add_argument("--zip", default="data_Q2_2019.zip")
    ap.add_argument("--out", default="project/ml/results/dataset_audit_revalidation")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    z = zipfile.ZipFile(a.zip)
    members = {i.filename: i for i in z.infolist() if not i.filename.startswith("__MACOSX")}
    ref_ts = Counter(i.date_time[:3] for i in members.values()).most_common(1)[0][0]
    rows, sci_rows = [], []
    for f in sorted(x for x in os.listdir(a.data) if x.endswith(".csv")):
        p = os.path.join(a.data, f)
        m = members.get(f)
        term, non_iso, sci_cols = conversion_markers(p)
        r = {"file": f, "local_size": os.path.getsize(p), "in_archive": m is not None,
             "archive_size": m.file_size if m else None,
             "archive_member_timestamp": "%04d-%02d-%02d %02d:%02d:%02d" % m.date_time if m else None,
             "crc_match": (m is not None and m.CRC == crc32_file(p) and m.file_size == os.path.getsize(p)),
             "line_terminator": term, "non_iso_date_rows": non_iso,
             "sci_notation_cells": sum(sci_cols.values())}
        if non_iso or r["sci_notation_cells"] or term not in ("CRLF", "LF"):
            with open(p, "rb") as fh:
                r["local_sha256"] = sha256_stream(fh)
            with z.open(f) as fh:
                r["archive_sha256"] = sha256_stream(fh)
            for c, n in sci_cols.items():
                sci_rows.append({"file": f, "column": c, "sci_notation_cells": n})
        rows.append(r)
        print(f"{f}: crc_match={r['crc_match']} term={term} non_iso={non_iso} sci={r['sci_notation_cells']}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.out, "provenance_check.csv"), index=False)
    pd.DataFrame(sci_rows, columns=["file", "column", "sci_notation_cells"]).sort_values(
        "sci_notation_cells", ascending=False).to_csv(
        os.path.join(a.out, "spreadsheet_conversion_cells.csv"), index=False)
    print(f"\nArchive: {a.zip}  members (excl. __MACOSX): {len(members)}  dominant member date: {ref_ts}")
    print(f"Local files: {len(df)}  CRC-identical to archive: {int(df['crc_match'].sum())}")
    print(f"Files with conversion markers: {df.loc[(df['non_iso_date_rows'] > 0) | (df['sci_notation_cells'] > 0) | ~df['line_terminator'].isin(['CRLF', 'LF']), 'file'].tolist()}")


if __name__ == "__main__":
    main()
