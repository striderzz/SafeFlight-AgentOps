"""A real CrewAI agent, task and crew, driven by FakeLLM: proves the tool-calling loop
works end to end without an API key."""

from crewai import Agent, Crew, Task
from crewai.tools import tool

from safeflight.llm import FakeLLM

CALLS: list[str] = []


@tool("lookup_rate")
def lookup_rate(carrier: str) -> str:
    """Accidents per million departures for an airline code."""
    CALLS.append(carrier)
    return {"MD": "0.11"}.get(carrier, "unknown")


def test_agent_calls_a_tool_and_answers():
    CALLS.clear()
    llm = FakeLLM(
        script=[
            'Thought: I need the rate for MD\nAction: lookup_rate\nAction Input: {"carrier": "MD"}',
            "Thought: I have the rate\nFinal Answer: Meridian Air (MD) has 0.11 accidents "
            "per million departures",
        ]
    )
    agent = Agent(
        role="Risk Analyst",
        goal="Report an airline's accident rate",
        backstory="You only report numbers that a tool returned.",
        llm=llm,
        tools=[lookup_rate],
        max_iter=3,
        verbose=False,
    )
    task = Task(description="What is MD's accident rate?", expected_output="One sentence", agent=agent)
    result = Crew(agents=[agent], tasks=[task], verbose=False).kickoff()

    assert CALLS == ["MD"]
    assert "0.11" in result.raw
    assert len(llm.calls) == 2
