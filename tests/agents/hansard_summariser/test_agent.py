"""Tests for digest.agents.hansard_summariser.agent module."""

from typing import Literal
from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from digest.agents.hansard_summariser.agent import (
    _get_default_model,
    _get_model_settings,
    create_editor_agent,
    create_summary_agent,
    create_tag_agent,
    create_title_agent,
)
from digest.agents.hansard_summariser.constants import ReasoningEffort
from digest.agents.hansard_summariser.schemas import DraftSummary, FinalSummary
from digest.agents.hansard_summariser.settings import (
    get_hansard_summariser_agent_settings,
)

AgentName = Literal["summary", "editor", "title", "tag"]
SummariserAgent = (
    Agent[None, DraftSummary]
    | Agent[str, FinalSummary]
    | Agent[None, str]
    | Agent[set[str], list[str]]
)


def _create_agent(name: AgentName) -> SummariserAgent:
    """Create the named summariser agent.

    Args:
        name: Which of the four summariser agents to create.

    Returns:
        The agent produced by that name's factory.
    """
    match name:
        case "summary":
            return create_summary_agent()
        case "editor":
            return create_editor_agent()
        case "title":
            return create_title_agent()
        case "tag":
            return create_tag_agent()


@pytest.mark.parametrize(
    ("name", "expected_output_type"),
    [
        ("summary", DraftSummary),
        ("editor", FinalSummary),
        ("title", str),
        ("tag", list[str]),
    ],
)
def test_factory_returns_agent_with_expected_output_type(
    name: AgentName, expected_output_type: type
) -> None:
    """Each factory returns an Agent producing that agent's output type.

    Args:
        name: Which agent factory this case exercises.
        expected_output_type: The output type that factory should declare.
    """
    agent = _create_agent(name)
    assert isinstance(agent, Agent)
    assert agent.output_type == expected_output_type


@pytest.mark.parametrize("name", ["summary", "editor", "title", "tag"])
def test_factory_returns_a_new_instance_each_call(name: AgentName) -> None:
    """Factories build a fresh agent per call rather than sharing one.

    Args:
        name: Which agent factory this case exercises.
    """
    assert _create_agent(name) is not _create_agent(name)


@pytest.mark.parametrize(
    ("name", "expected_fragments"),
    [
        ("summary", ("Summarise one day", "politically neutral")),
        ("title", ("headline", "title-case")),
    ],
)
def test_agent_has_static_system_prompt(
    name: AgentName, expected_fragments: tuple[str, ...]
) -> None:
    """Agents with a static prompt register exactly one, with the right content.

    Args:
        name: Which agent factory this case exercises.
        expected_fragments: Substrings the static prompt must contain.
    """
    agent = _create_agent(name)
    assert len(agent._system_prompts) == 1
    prompt = agent._system_prompts[0]
    for fragment in expected_fragments:
        assert fragment in prompt


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


def test_default_model_uses_configured_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model name comes from settings, not a module constant.

    Args:
        monkeypatch: Pytest fixture for patching settings attributes.
    """
    monkeypatch.setattr(get_hansard_summariser_agent_settings(), "model", "test-model")
    model = _get_default_model()
    assert isinstance(model, OpenAIResponsesModel)
    assert model.model_name == "test-model"


def test_default_model_name_is_luna() -> None:
    """The shipped default is the model this migration targets."""
    model = _get_default_model()
    assert isinstance(model, OpenAIResponsesModel)
    assert model.model_name == "gpt-5.6-luna"


def test_get_model_settings_carries_effort_and_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model settings carry the requested effort and the configured ceiling.

    Args:
        monkeypatch: Pytest fixture for patching settings attributes.
    """
    monkeypatch.setattr(get_hansard_summariser_agent_settings(), "max_tokens", 4096)
    assert _get_model_settings("xhigh") == OpenAIResponsesModelSettings(
        openai_reasoning_effort="xhigh", max_tokens=4096
    )


@pytest.mark.parametrize(
    ("name", "expected_effort"),
    [
        ("summary", "none"),
        ("editor", "low"),
        ("title", "high"),
        ("tag", "xhigh"),
    ],
)
def test_each_agent_uses_its_own_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
    name: AgentName,
    expected_effort: ReasoningEffort,
) -> None:
    """Each factory reads its own effort setting and not another agent's.

    All four effort settings are patched to four distinct values on every
    case, so a factory that reads another agent's field is still caught even
    though only one factory is exercised per case.

    Args:
        monkeypatch: Pytest fixture for patching settings attributes.
        name: Which agent factory this case exercises.
        expected_effort: The reasoning effort that factory should pick up.
    """
    monkeypatch.setattr(
        get_hansard_summariser_agent_settings(), "summary_reasoning_effort", "none"
    )
    monkeypatch.setattr(
        get_hansard_summariser_agent_settings(), "editor_reasoning_effort", "low"
    )
    monkeypatch.setattr(
        get_hansard_summariser_agent_settings(), "title_reasoning_effort", "high"
    )
    monkeypatch.setattr(
        get_hansard_summariser_agent_settings(), "tag_reasoning_effort", "xhigh"
    )

    assert _create_agent(name).model_settings == _get_model_settings(expected_effort)


@pytest.mark.parametrize(
    ("name", "expected_effort"),
    [
        ("summary", "medium"),
        ("editor", "high"),
        ("title", "low"),
        ("tag", "low"),
    ],
)
def test_shipped_efforts_match_the_migration_defaults(
    name: AgentName, expected_effort: ReasoningEffort
) -> None:
    """Summary runs at medium, editor at high; title and tag run at low.

    Args:
        name: Which agent factory this case exercises.
        expected_effort: The effort that agent ships with.
    """
    assert _create_agent(name).model_settings == _get_model_settings(expected_effort)
