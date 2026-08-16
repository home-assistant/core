"""Sofar Inverter Modbus — built on modbus-connection.

This module owns the ModbusConnection and the coordinator; sofar-modbus is
the HA-free device library that does the actual register work.

Only the switch platform is wired up so far — this integration is being
added to Core in a sequence of PRs, one platform at a time. PLATFORMS grows
as each subsequent platform lands.
"""

import logging

from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .connection import build_connection, unit_id
from .const import CONF_READ_EPS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    connection = build_connection(entry.data)
    entry.async_on_unload(connection.close)

    unit = connection.for_unit(unit_id(entry.data))
    serial = entry.unique_id
    inverter_type, model = identify(serial) if serial else (None, None)
    device = SofarInverter(
        unit, inverter_type=inverter_type, read_eps=entry.data.get(CONF_READ_EPS, False)
    )
    if serial and inverter_type and device.inverter_type is not None:
        device.prime(serial, model)

    coordinator = SofarDataUpdateCoordinator(
        hass, entry, connection, device, DEFAULT_SCAN_INTERVAL
    )

    if not device.inverter_type:
        # Fallback for entries where inverter type could not be determined in-memory:
        # poll the device to discover its identity block.
        await coordinator.async_config_entry_first_refresh()
        if not device.inverter_type:
            raise ConfigEntryNotReady(
                f"Unrecognized Sofar inverter model for {entry.title}"
            )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if serial and inverter_type:

        async def _async_startup_refresh() -> None:
            await coordinator.async_refresh()
            await coordinator.async_refresh_slow_tier()

        entry.async_create_background_task(
            hass,
            _async_startup_refresh(),
            name=f"{DOMAIN}_{entry.unique_id}_startup_refresh",
        )
    else:
        entry.async_create_background_task(
            hass,
            coordinator.async_refresh_slow_tier(),
            name=f"{DOMAIN}_{entry.unique_id}_initial_slow_refresh",
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
