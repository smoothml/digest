"""Tests for digest.agents.hansard_summariser.agent module."""

from typing import Literal

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

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
_TRANSCRIPT = "Test transcript content"
_EXISTING_TAGS = {"economy", "healthcare"}
_DISTINCT_EFFORTS: dict[AgentName, ReasoningEffort] = {
    "summary": "none",
    "editor": "low",
    "title": "high",
    "tag": "xhigh",
}


class _PromptsCapturedError(Exception):
    """Raised by the stand-in model to stop a run once it has the prompts."""

    def __init__(self, system_prompts: list[str]) -> None:
        super().__init__("system prompts captured")
        self.system_prompts = system_prompts


def _capture_system_prompts(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    """Stop the run, carrying the system prompts the agent sent to the model.

    Args:
        messages: Messages the agent sent to the model.
        info: Details of the agent run, unused.

    Raises:
        _PromptsCapturedError: Always, carrying the system prompts.
    """
    raise _PromptsCapturedError(
        [
            part.content
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, SystemPromptPart)
        ]
    )


async def _run_capturing_system_prompts[DepsT, OutputT](
    agent: Agent[DepsT, OutputT], deps: DepsT
) -> list[str]:
    """Run an agent against a stand-in model and return the system prompts sent.

    Args:
        agent: The agent to run.
        deps: Dependencies for the run.

    Returns:
        The system prompts the agent sent to the model.
    """
    with (
        agent.override(model=FunctionModel(_capture_system_prompts)),
        pytest.raises(_PromptsCapturedError) as captured,
    ):
        await agent.run("Draft summary", deps=deps)
    return captured.value.system_prompts


async def _system_prompts_sent_by(name: AgentName) -> list[str]:
    """Return the system prompts the named agent sends to its model.

    Args:
        name: Which of the four summariser agents to run.

    Returns:
        The system prompts the agent sent.
    """
    match name:
        case "summary":
            return await _run_capturing_system_prompts(create_summary_agent(), None)
        case "editor":
            return await _run_capturing_system_prompts(
                create_editor_agent(), _TRANSCRIPT
            )
        case "title":
            return await _run_capturing_system_prompts(create_title_agent(), None)
        case "tag":
            return await _run_capturing_system_prompts(
                create_tag_agent(), _EXISTING_TAGS
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
        pytest.param(
            "summary", ("Summarise one day", "politically neutral"), id="summary"
        ),
        pytest.param(
            "editor", (_TRANSCRIPT, "rigorous, impartial editor"), id="editor"
        ),
        pytest.param("title", ("headline", "title-case"), id="title"),
        pytest.param("tag", (*_EXISTING_TAGS, "Generate 1-5 tags"), id="tag"),
    ],
)
async def test_agent_sends_its_system_prompt(
    name: AgentName, expected_fragments: tuple[str, ...]
) -> None:
    """Each agent sends one system prompt, filled from its dependencies if any.

    Args:
        name: Which agent factory this case exercises.
        expected_fragments: Substrings the sent prompt must contain.
    """
    prompts = await _system_prompts_sent_by(name)

    assert len(prompts) == 1
    for fragment in expected_fragments:
        assert fragment in prompts[0]


def test_default_model_uses_configured_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model name comes from settings, not a module constant.

    Args:
        monkeypatch: Pytest fixture for patching settings attributes.
    """
    monkeypatch.setattr(get_hansard_summariser_agent_settings(), "model", "test-model")
    assert _get_default_model().model_name == "test-model"


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


@pytest.mark.parametrize(("name", "expected_effort"), _DISTINCT_EFFORTS.items())
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
    settings = get_hansard_summariser_agent_settings()
    for agent_name, effort in _DISTINCT_EFFORTS.items():
        monkeypatch.setattr(settings, f"{agent_name}_reasoning_effort", effort)

    assert _create_agent(name).model_settings == _get_model_settings(expected_effort)
