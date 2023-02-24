"""The Thread integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.exceptions import HomeAssistantError

from python_otbr_api.tlv_parser import TLVError

from .const import (
    DOMAIN,
    SERVICE_ADD_DATASET,
    SERVICE_DELETE_DATASET,
    ATTR_TLV,
    ATTR_ID,
)
from .dataset_store import (
    DatasetEntry,
    async_add_dataset,
    async_get_preferred_dataset,
    async_delete_dataset,
)
from .websocket_api import async_setup as async_setup_ws_api

__all__ = [
    "DOMAIN",
    "DatasetEntry",
    "async_add_dataset",
    "async_get_preferred_dataset",
]


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

    async def add_dataset(service: ServiceCall) -> None:
        tlv: str = service.data[ATTR_TLV]
        try:
            await async_add_dataset(hass, "user", tlv)
        except TLVError as exc:
            raise HomeAssistantError("Invalid TLV")
        return

    async def delete_dataset(service: ServiceCall) -> None:
        id: str = service.data[ATTR_ID]
        await async_delete_dataset(hass, id)
        return

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ADD_DATASET,
        add_dataset,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TLV): cv.string,
            }
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_DATASET,
        delete_dataset,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ID): cv.string,
            }
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
