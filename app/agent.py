"""Hosted Analytics Agent — Google ADK root agent.

Run locally (from the repo root, after `pip install -r requirements.txt`):

    adk web          # dev UI at http://localhost:8000, pick "app"
    adk run app      # terminal chat

Model auth: Vertex AI via Application Default Credentials (see .env.example),
so no model API key is stored anywhere.
"""
from google.adk.agents.llm_agent import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from .config import CONFIG
from .data_dictionary import build_instruction
from .learning import learned_section
from .tools.bq_tools import list_tables, run_query, show_schema

_BASE_INSTRUCTION = build_instruction()


def _instruction(_: ReadonlyContext) -> str:
    """Dynamic instruction: static semantic layer + learned examples (D7).

    ADK calls this on every model request, so freshly learned examples reach
    the agent without a restart. learned_section() is cached and can never
    raise — worst case it contributes nothing.
    """
    return _BASE_INSTRUCTION + learned_section()


root_agent = Agent(
    name="hosted_analytics_agent",
    model=CONFIG.model,
    description=(
        "Answers natural-language questions about US Department of Defense "
        "contract awards (USAspending FY2024-FY2025) by writing and running "
        "read-only BigQuery SQL."
    ),
    instruction=_instruction,
    tools=[list_tables, show_schema, run_query],
)
