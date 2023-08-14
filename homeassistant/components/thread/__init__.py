"""The Thread integration."""
from __future__ import annotations

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .dataset_store import (
    DatasetEntry,
    async_add_dataset,
    async_get_dataset,
    async_get_preferred_border_agent_id,
    async_get_preferred_dataset,
    async_set_preferred_border_agent_id,
)
from .websocket_api import async_setup as async_setup_ws_api

__all__ = [
    "DOMAIN",
    "DatasetEntry",
    "async_add_dataset",
    "async_get_preferred_border_agent_id",
    "async_get_dataset",
    "async_get_preferred_dataset",
    "async_set_preferred_border_agent_id",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Thread integration."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )
    async_setup_ws_api(hass)
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
