"""Integrate De Dietrich devices into Home Assistant."""

import logging

import diematic_modbus
from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import CONF_UNIT_ID, DOMAIN, MESSAGE_SPACING, MODBUS_FRAMER
from .coordinator import DeDietrichConfigEntry, DeDietrichDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: DeDietrichConfigEntry) -> bool:
    """Set up De Dietrich from a config entry."""
    try:
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
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err
    unit.set_message_spacing(MESSAGE_SPACING)

    try:
        detection = await diematic_modbus.async_detect(unit)
    except diematic_modbus.DiematicProbeError as err:
        outcomes = [
            block.outcome
            for block in (*err.detection.base_probe, *err.detection.isystem_probe)
        ]
        _LOGGER.error(
            "%s: Diematic detection failed: %s, probe outcomes: %s",
            entry.title,
            err.detection,
            outcomes,
            exc_info=err,
        )
        if any(
            block.outcome == "error"
            for block in (*err.detection.base_probe, *err.detection.isystem_probe)
        ):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_device",
            translation_placeholders={"error": str(err)},
        ) from err
    except ModbusError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="modbus_error",
        ) from err

    assert detection.device is not None
    device = detection.device
    coordinator = DeDietrichDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeDietrichConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
