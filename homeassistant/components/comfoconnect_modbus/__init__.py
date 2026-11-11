"""Integrate Zehnder ventilation units through a ComfoConnect PRO gateway."""

from comfoconnect_pro_modbus import ComfoConnectPro

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import (
    ComfoConnectProConfigEntry,
    ComfoConnectProDataUpdateCoordinator,
    ComfoConnectProRuntimeData,
)
from .helpers import create_modbus_params

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
        # Another entry holds the same port or host with other link settings
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
        ) from err
    coordinator = ComfoConnectProDataUpdateCoordinator(
        hass, entry, ComfoConnectPro(unit)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ComfoConnectProRuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: ComfoConnectProConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
