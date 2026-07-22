"""Create aim_analytics.agent_feedback — the store behind the agent's
self-learning loop (decision D7).

One row per thumbs-up/down a user gives an answer in the web UI. The learning
module reads back thumbs-up rows and turns validated question->SQL pairs into
few-shot examples in the agent's instruction.

Run once with owner ADC:  python data/create_feedback_table.py
Idempotent: exits cleanly if the table already exists.
"""
import sys
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import Conflict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import CONFIG  # noqa: E402

TABLE_ID = f"{CONFIG.project_id}.aim_analytics.agent_feedback"

SCHEMA = [
    bigquery.SchemaField("ts", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING"),
    bigquery.SchemaField("question", "STRING"),
    bigquery.SchemaField("sql", "STRING"),
    bigquery.SchemaField("answer", "STRING"),
    bigquery.SchemaField("rating", "STRING", mode="REQUIRED"),  # 'up' | 'down'
    bigquery.SchemaField("comment", "STRING"),
    bigquery.SchemaField("model", "STRING"),
    bigquery.SchemaField("build_id", "STRING"),
]


def main() -> None:
    client = bigquery.Client(project=CONFIG.project_id, location=CONFIG.bq_location)
    table = bigquery.Table(TABLE_ID, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY, field="ts")
    table.description = ("User feedback on agent answers (self-learning loop, D7). "
                         "Thumbs-up rows feed learned examples; comments are for "
                         "human review only and never enter the prompt.")
    try:
        client.create_table(table)
        print("created", TABLE_ID)
    except Conflict:
        print("already exists", TABLE_ID)


if __name__ == "__main__":
    main()
