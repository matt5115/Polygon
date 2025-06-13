#!/usr/bin/env python3
"""
Parse strategy_comparison.md, apply thresholds from
config/selection_criteria.yaml, and write build/winner.txt.
"""
import argparse
import sys
import yaml
import textwrap
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MD = ROOT / "build" / "strategy_comparison.md"
YAML_CR = ROOT / "config" / "selection_criteria.yaml"
OUT = ROOT / "build" / "winner.txt"

# ---------- helpers ----------

def parse_table(md: str):
    """Return list[dict] from a GitHub-flavored markdown table."""
    lines = [ln.strip() for ln in md.splitlines() if ln.strip().startswith("|")]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].strip("|").split("|")]
    body = lines[2:]  # skip divider row (|----|)
    rows = []
    for ln in body:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


def keep(row, crit):
    """Return True if row meets the threshold criteria."""
    def _pct(s):
        return float(str(s).rstrip("%"))

    try:
        roi = _pct(row.get("ROI %", 0))
        dd = _pct(row.get("DD %", 0))
        sharpe = float(row.get("Sharpe", 0))
    except ValueError:
        return False
    return (
        roi >= crit.get("ROI", -float("inf"))
        and dd <= crit.get("DD", float("inf"))
        and sharpe >= crit.get("Sharpe", -float("inf"))
    )


# ---------- main ----------

def main(argv=None):
    argv = argv or sys.argv[1:]
    p = argparse.ArgumentParser(description="Select strategy winner from markdown table")
    p.add_argument("--md", default=MD, type=pathlib.Path, help="Path to strategy_comparison.md")
    p.add_argument("--criteria", default=YAML_CR, type=pathlib.Path, help="Selection criteria YAML file")
    p.add_argument("--out", default=OUT, type=pathlib.Path, help="File to write winning slug to")
    ns = p.parse_args(argv)

    if not ns.md.exists():
        sys.exit(f"Markdown table not found: {ns.md}")
    if not ns.criteria.exists():
        sys.exit(f"Criteria YAML not found: {ns.criteria}")

    table = parse_table(ns.md.read_text())
    crit = yaml.safe_load(ns.criteria.read_text()) or {}

    survivors = [r for r in table if keep(r, crit)]
    if not survivors:
        sys.exit("❌  No strategy met the selection criteria.")

    # pick max Sharpe, tie-break on highest ROI
    winner = max(
        survivors,
        key=lambda r: (float(r["Sharpe"]), float(str(r["ROI %"]).rstrip("%"))),
    )
    slug = winner["Slug"]

    ns.out.write_text(slug + "\n")

    try:
        rel_out = ns.out.relative_to(ROOT)
    except ValueError:
        rel_out = ns.out
    print(f"✅  Winner: {slug} → {rel_out}")


if __name__ == "__main__":
    main()
