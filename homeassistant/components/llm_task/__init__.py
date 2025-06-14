"""Integration to offer LLM tasks to Home Assistant.

LLM tasks provide a way to use conversation agents for general purpose tasks
outside of an assistant pipeline (e.g. use for summarization in the frontend). This
exposes a conversation agent LLM for general use, without user prompts or customizations.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, storage
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .const import DATA_COMPONENT, DATA_PREFERENCES, DOMAIN
from .entity import LLMTaskEntity
from .http import async_setup as async_setup_conversation_http
from .task import LLMTask, LLMTaskResult, LLMTaskType, async_run_task

__all__ = [
    "DOMAIN",
    "LLMTask",
    "LLMTaskEntity",
    "LLMTaskResult",
    "LLMTaskType",
    "async_run_task",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    hass.data[DATA_PREFERENCES] = LLMTaskPreferences(hass)
    await hass.data[DATA_PREFERENCES].async_load()
    hass.data[DATA_COMPONENT] = EntityComponent[LLMTaskEntity](_LOGGER, DOMAIN, hass)
    async_setup_conversation_http(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class LLMTaskPreferences:
    """LLM Task preferences."""

    summary_entity_id: str | None = None
    generate_entity_id: str | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the preferences."""
        self._store: storage.Store[dict[str, str | None]] = storage.Store(
            hass, 1, DOMAIN
        )

    async def async_load(self) -> None:
        """Load the data from the store."""
        data = await self._store.async_load()
        if data is None:
            return
        self.summary_entity_id = data.get("summary_entity_id")
        self.generate_entity_id = data.get("generate_entity_id")

    @callback
    def async_set_preferences(
        self,
        *,
        summary_entity_id: str | None | UndefinedType = UNDEFINED,
        generate_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> None:
        """Set the preferences."""
        changed = False
        for key, value in (
            ("summary_entity_id", summary_entity_id),
            ("generate_entity_id", generate_entity_id),
        ):
            if value is not UNDEFINED:
                if getattr(self, key) != value:
                    setattr(self, key, value)
                    changed = True

        if not changed:
            return

        self._store.async_delay_save(
            lambda: {
                "summary_entity_id": self.summary_entity_id,
                "generate_entity_id": self.generate_entity_id,
            },
            10,
        )

    @callback
    def as_dict(self) -> dict[str, str | None]:
        """Get the current preferences."""
        return {
            "summary_entity_id": self.summary_entity_id,
            "generate_entity_id": self.generate_entity_id,
        }
