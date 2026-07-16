"""Hosted Analytics Agent — Google ADK root agent.

Run locally (from the repo root, after `pip install -r requirements.txt`):

    adk web          # dev UI at http://localhost:8000, pick "app"
    adk run app      # terminal chat

Model auth: Vertex AI via Application Default Credentials (see .env.example),
so no model API key is stored anywhere.
"""
from google.adk.agents.llm_agent import Agent

from .config import CONFIG
from .data_dictionary import build_instruction
from .tools.bq_tools import list_tables, run_query, show_schema

root_agent = Agent(
    name="hosted_analytics_agent",
    model=CONFIG.model,
    description=(
        "Answers natural-language questions about US Department of Defense "
        "contract awards (USAspending FY2024-FY2025) by writing and running "
        "read-only BigQuery SQL."
    ),
    instruction=build_instruction(),
    tools=[list_tables, show_schema, run_query],
)
