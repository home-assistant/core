"""LLM tasks to be handled by agents."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant

from .const import DATA_COMPONENT, LLMTaskType


async def async_run_task(
    hass: HomeAssistant,
    task_name: str,
    entity_id: str,
    task_type: LLMTaskType,
    prompt: str,
) -> LLMTaskResult:
    """Run a task in the LLM Task integration."""
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        raise ValueError(f"LLM Task entity {entity_id} not found")

    return await entity.internal_async_handle_llm_task(
        LLMTask(
            name=task_name,
            type=task_type,
            prompt=prompt,
        )
    )


@dataclass(slots=True)
class LLMTask:
    """LLM task to be processed."""

    name: str
    """Name of the task."""

    type: LLMTaskType
    """Type of the task."""

    prompt: str
    """Prompt for the LLM."""

    def __str__(self) -> str:
        """Return task as a string."""
        return f"<LLMTask {self.type}: {id(self)}>"


@dataclass(slots=True)
class LLMTaskResult:
    """Result of LLM task."""

    conversation_id: str
    """Unique identifier for the conversation."""

    result: str
    """Result of the task."""

    def as_dict(self) -> dict[str, str]:
        """Return result as a dict."""
        return {
            "conversation_id": self.conversation_id,
            "result": self.result,
        }
