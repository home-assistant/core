"""The PowerShades integration."""

import logging

from pyowershades import (
    OP_GET_SERIAL,
    PowerShadesConnection,
    PowerShadesTimeoutError,
    parse_serial_reply,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator
from .discovery import async_start_discovery

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_update_device_model(
    hass: HomeAssistant,
    entry: PowerShadesConfigEntry,
    coordinator: PowerShadesCoordinator,
) -> None:
    """Fill in the model if missing from the entry."""
    if entry.data.get("model") is not None:
        return

    try:
        reply = await coordinator.connection.async_request(OP_GET_SERIAL)
    except PowerShadesTimeoutError:
        return
    parsed = parse_serial_reply(reply)
    if parsed is not None:
        coordinator.model = parsed["model"]
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "model": parsed["model"]}
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PowerShades component."""
    async_start_discovery(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PowerShadesConfigEntry) -> bool:
    """Set up PowerShades from a config entry."""
    connection = PowerShadesConnection(entry.data["ip"])
    await connection.async_connect()

    coordinator = PowerShadesCoordinator(hass, entry, connection)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        connection.close()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(connection.close)

    await _async_update_device_model(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowerShadesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
