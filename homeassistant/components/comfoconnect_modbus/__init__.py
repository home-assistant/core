"""Integrate Zehnder ventilation units through a ComfoConnect PRO gateway."""

from comfoconnect_pro_modbus import ComfoConnectPro

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .config_flow import create_modbus_params
from .const import CONF_UNIT_ID
from .coordinator import (
    ComfoConnectProConfigEntry,
    ComfoConnectProDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ComfoConnectProConfigEntry
) -> None:
    """Set up a ComfoConnect PRO from a config entry."""
    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        ) from err
    coordinator = ComfoConnectProDataUpdateCoordinator(
        hass, entry, ComfoConnectPro(unit)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: ComfoConnectProConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
