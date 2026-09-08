"""Integrate De Dietrich devices into Home Assistant."""

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import CONF_SYSTEM, CONF_UNIT_ID, DOMAIN, MESSAGE_SPACING, MODBUS_FRAMER
from .coordinator import DeDietrichConfigEntry, DeDietrichDataUpdateCoordinator
from .device import build_device

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

    device = build_device(unit, entry.data[CONF_SYSTEM])

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
