"""Tests for digest.agents.hansard_summariser.agent module."""

from unittest.mock import MagicMock

from pydantic_ai import Agent

from digest.agents.hansard_summariser.agent import (
    create_editor_agent,
    create_summary_agent,
    create_tag_agent,
    create_title_agent,
)
from digest.agents.hansard_summariser.schemas import DraftSummary, FinalSummary


def test_create_summary_agent_returns_agent() -> None:
    """Factory returns an Agent with correct output type."""
    agent = create_summary_agent()
    assert isinstance(agent, Agent)


def test_create_summary_agent_has_correct_output_type() -> None:
    """Summary agent should output DraftSummary."""
    agent = create_summary_agent()
    assert agent.output_type is DraftSummary


def test_create_editor_agent_returns_agent() -> None:
    """Factory returns an Agent with correct output type."""
    agent = create_editor_agent()
    assert isinstance(agent, Agent)


def test_create_editor_agent_has_correct_output_type() -> None:
    """Editor agent should output FinalSummary."""
    agent = create_editor_agent()
    assert agent.output_type is FinalSummary


def test_create_title_agent_returns_agent() -> None:
    """Factory returns an Agent with correct output type."""
    agent = create_title_agent()
    assert isinstance(agent, Agent)


def test_create_title_agent_has_correct_output_type() -> None:
    """Title agent should output str."""
    agent = create_title_agent()
    assert agent.output_type is str


def test_create_tag_agent_returns_agent() -> None:
    """Factory returns an Agent with correct output type."""
    agent = create_tag_agent()
    assert isinstance(agent, Agent)


def test_create_tag_agent_has_correct_output_type() -> None:
    """Tag agent should output list[str]."""
    agent = create_tag_agent()
    assert agent.output_type == list[str]


def test_factory_functions_return_new_instances() -> None:
    """Factory functions return new instances each time."""
    summary_agent1 = create_summary_agent()
    summary_agent2 = create_summary_agent()
    assert summary_agent1 is not summary_agent2

    editor_agent1 = create_editor_agent()
    editor_agent2 = create_editor_agent()
    assert editor_agent1 is not editor_agent2

    title_agent1 = create_title_agent()
    title_agent2 = create_title_agent()
    assert title_agent1 is not title_agent2

    tag_agent1 = create_tag_agent()
    tag_agent2 = create_tag_agent()
    assert tag_agent1 is not tag_agent2


def test_summary_agent_has_system_prompt() -> None:
    """Summary agent has a static system prompt about summarising debates."""
    agent = create_summary_agent()
    assert len(agent._system_prompts) == 1
    prompt = agent._system_prompts[0]
    assert "Summarise one day" in prompt
    assert "politically neutral" in prompt


def test_title_agent_has_system_prompt() -> None:
    """Title agent has a static system prompt about generating headlines."""
    agent = create_title_agent()
    assert len(agent._system_prompts) == 1
    prompt = agent._system_prompts[0]
    assert "headline" in prompt
    assert "title-case" in prompt


async def test_editor_agent_registers_dynamic_system_prompt() -> None:
    """Editor agent registers a dynamic system prompt that includes the transcript."""
    agent = create_editor_agent()
    assert len(agent._system_prompt_functions) == 1

    ctx = MagicMock()
    ctx.deps = "Test transcript content"
    prompt = await agent._system_prompt_functions[0].run(ctx)
    assert prompt is not None
    assert "Test transcript content" in prompt
    assert "rigorous, impartial editor" in prompt


async def test_tag_agent_registers_dynamic_system_prompt() -> None:
    """Tag agent registers a dynamic system prompt that includes existing tags."""
    agent = create_tag_agent()
    assert len(agent._system_prompt_functions) == 1

    ctx = MagicMock()
    ctx.deps = {"economy", "healthcare"}
    prompt = await agent._system_prompt_functions[0].run(ctx)
    assert prompt is not None
    assert "economy" in prompt
    assert "healthcare" in prompt
    assert "Generate 1-5 tags" in prompt
