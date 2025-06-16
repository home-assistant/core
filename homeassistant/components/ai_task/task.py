"""AI tasks to be handled by agents."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant

from .const import DATA_COMPONENT, DATA_PREFERENCES, GenTextTaskType


async def async_generate_text(
    hass: HomeAssistant,
    *,
    task_name: str,
    entity_id: str | None = None,
    task_type: GenTextTaskType,
    instructions: str,
) -> GenTextTaskResult:
    """Run a task in the AI Task integration."""
    if entity_id is None:
        preferences = hass.data[DATA_PREFERENCES]
        if task_type == GenTextTaskType.SUMMARY:
            entity_id = preferences.gen_text_summary_entity_id
        elif task_type == GenTextTaskType.GENERATE:
            entity_id = preferences.gen_text_generate_entity_id

    if entity_id is None:
        raise ValueError(
            "No entity_id provided and no preferred entity set for this task type"
        )

    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        raise ValueError(f"AI Task entity {entity_id} not found")

    return await entity.internal_async_generate_text(
        GenTextTask(
            name=task_name,
            type=task_type,
            instructions=instructions,
        )
    )


@dataclass(slots=True)
class GenTextTask:
    """Gen text task to be processed."""

    name: str
    """Name of the task."""

    type: GenTextTaskType
    """Type of the task."""

    instructions: str
    """Instructions on what needs to be done."""

    def __str__(self) -> str:
        """Return task as a string."""
        return f"<GenTextTask {self.type}: {id(self)}>"


@dataclass(slots=True)
class GenTextTaskResult:
    """Result of gen text task."""

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
