"""Pull the four extracts from the public GA4 sample in BigQuery -> data/raw/*.parquet.

Usage:
    gcloud auth application-default login
    python -m ga4funnel.extract --project YOUR_GCP_PROJECT_ID

Each query is dry-run first so you can see the bytes scanned (the BigQuery
sandbox gives 1 TB of free querying per month; this pulls a few GB at most).
"""
import argparse

from .config import RAW_DIR, RAW_TABLES, SQL_BQ

MAX_BYTES_BILLED = 30 * 1024**3  # hard safety cap per query: 30 GB


def render(name: str) -> str:
    sql = (SQL_BQ / f"{name}.sql").read_text()
    if "{{events_cte}}" in sql:
        sql = sql.replace("{{events_cte}}", (SQL_BQ / "_events_cte.sql").read_text())
    return sql


def main() -> None:
    from google.cloud import bigquery

    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Your GCP project id (billing/sandbox project)")
    args = ap.parse_args()

    client = bigquery.Client(project=args.project)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for name in RAW_TABLES:
        sql = render(name)
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
        print(f"[{name}] will scan {dry.total_bytes_processed / 1024**3:.2f} GB")
        job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES_BILLED))
        df = job.to_dataframe()
        path = RAW_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"[{name}] {len(df):,} rows -> {path.relative_to(RAW_DIR.parent.parent)}")

    (RAW_DIR / "SOURCE").write_text("bigquery\n")
    print("Done. Next: python -m ga4funnel.run")


if __name__ == "__main__":
    main()
