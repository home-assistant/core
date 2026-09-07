"""Integrate De Dietrich Diematic devices into Home Assistant."""

import logging

from diematic_modbus import Diematic, DiematicISystem
from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import CONF_SYSTEM, CONF_UNIT_ID, DOMAIN, MESSAGE_SPACING, MODBUS_FRAMER
from .coordinator import DeDietrichConfigEntry, DeDietrichDataUpdateCoordinator
from .device import build_device

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

_IDENTITY_ATTEMPTS = 3

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_read_identity(
    entry: DeDietrichConfigEntry, device: Diematic | DiematicISystem
) -> None:
    """Read identity once, retrying a few times against a transient blip."""
    for attempt in range(_IDENTITY_ATTEMPTS):
        try:
            await device.identity.async_update()
        except ModbusError as err:
            if attempt == _IDENTITY_ATTEMPTS - 1:
                _LOGGER.warning("%s: could not read identity: %s", entry.title, err)
        else:
            return


async def async_setup_entry(hass: HomeAssistant, entry: DeDietrichConfigEntry) -> bool:
    """Set up De Dietrich Diematic Modbus from a config entry."""
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            framer=MODBUS_FRAMER,
        ),
        entry.data[CONF_UNIT_ID],
    )
    unit.set_message_spacing(MESSAGE_SPACING)

    device = build_device(unit, entry.data[CONF_SYSTEM])

    coordinator = DeDietrichDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_refresh()

    # Not tied to the coordinator: identity never changes once read.
    await _async_read_identity(entry, device)

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeDietrichConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
