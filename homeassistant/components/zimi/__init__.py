"""The zcc integration."""

from __future__ import annotations

import logging

from zcc import ControlPoint, ControlPointError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, PLATFORMS
from .helpers import async_connect_to_controller

_LOGGER = logging.getLogger(__name__)


type ZimiConfigEntry = ConfigEntry[ControlPoint]


async def async_setup_entry(hass: HomeAssistant, entry: ZimiConfigEntry) -> bool:
    """Connect to Zimi Controller and register device."""
    _LOGGER.debug("Zimi setup starting")

    try:
        api = await async_connect_to_controller(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )

    except ControlPointError as error:
        _LOGGER.error("Initiation failed: %s", error)
        raise ConfigEntryNotReady(error) from error

    if not api:
        msg = "Zimi setup failed: not ready"
        _LOGGER.error(msg=msg)
        raise ConfigEntryNotReady(msg)

    _LOGGER.debug("\n%s", api.describe())

    entry.runtime_data = api

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, api.mac)},
        manufacturer=api.brand,
        name=f"ZCC ({api.host}:{api.port})",
        model=api.product,
        model_id="Zimi Cloud Connect",
        hw_version=api.firmware_version,
        sw_version=api.api_version,
        connections={(CONNECTION_NETWORK_MAC, api.mac)},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Zimi setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZimiConfigEntry) -> bool:
    """Unload a config entry."""

    api = entry.runtime_data
    if api:
        api.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
