"""Run the full local pipeline: data/raw/*.parquet -> outputs/ (CSV for Tableau, parquet for the app, findings.md).

Usage:  python -m ga4funnel.run
"""
from . import findings
from .config import OUT_DIR, RAW_DIR
from .pipeline import analyse, connect_parquet


def main() -> None:
    source_file = RAW_DIR / "SOURCE"
    source = source_file.read_text().strip() if source_file.exists() else "unknown"
    con = connect_parquet(RAW_DIR)
    tables = analyse(con)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        df.to_parquet(OUT_DIR / f"{name}.parquet", index=False)
    (OUT_DIR / "SOURCE").write_text(source + "\n")
    brief = findings.build(tables, source)
    (OUT_DIR / "findings.md").write_text(brief)
    print(brief)
    print(f"Wrote {len(tables)} tables + findings.md to {OUT_DIR}")


if __name__ == "__main__":
    main()
