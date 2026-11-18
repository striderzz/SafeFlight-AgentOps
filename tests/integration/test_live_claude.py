"""Live spike: ClaudeLLM inside a CrewAI agent, calling a tool, on the real API.
Skipped unless ANTHROPIC_API_KEY is set; CI never runs it."""

import os

import pytest
from crewai import Agent, Crew, Task
from crewai.tools import tool

from safeflight.llm import ClaudeLLM, run_scope

pytestmark = pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")

SEEN: list[str] = []


@tool("lookup_rate")
def lookup_rate(carrier: str) -> str:
    """Accidents per million departures for an airline code, e.g. MD."""
    SEEN.append(carrier)
    return "0.11" if carrier == "MD" else "unknown"


def test_claude_agent_uses_the_tool_and_logs_cost(ledger):
    agent = Agent(
        role="Risk Analyst",
        goal="Report an airline's accident rate using the tool",
        backstory="You never state a number the tool did not return.",
        llm=ClaudeLLM.for_role("scout"),
        tools=[lookup_rate],
        max_iter=4,
    )
    task = Task(
        description="Use lookup_rate to get the rate for airline code MD, then report it.",
        expected_output="One sentence with the rate",
        agent=agent,
    )
    with run_scope("live_spike"):
        result = Crew(agents=[agent], tasks=[task]).kickoff()
    assert "MD" in SEEN
    assert "0.11" in result.raw
    calls = ledger.calls("live_spike")
    assert calls and all(c["usd"] > 0 for c in calls)
