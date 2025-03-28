"""The Model Context Protocol integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import DOMAIN
from .coordinator import ModelContextProtocolCoordinator
from .types import ModelContextProtocolConfigEntry

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]

API_PROMPT = "The following tools are available from a remote server named {name}."


async def async_setup_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Set up Model Context Protocol from a config entry."""
    coordinator = ModelContextProtocolCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    unsub = llm.async_register_api(
        hass,
        ModelContextProtocolAPI(
            hass=hass,
            id=f"{DOMAIN}-{entry.entry_id}",
            name=entry.title,
            coordinator=coordinator,
        ),
    )
    entry.async_on_unload(unsub)

    entry.runtime_data = coordinator

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


@dataclass(kw_only=True)
class ModelContextProtocolAPI(llm.API):
    """Define an object to hold the Model Context Protocol API."""

    coordinator: ModelContextProtocolCoordinator

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            self,
            API_PROMPT.format(name=self.name),
            llm_context,
            tools=self.coordinator.data,
        )
