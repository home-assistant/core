"""NeoPool integration for Home Assistant."""

from neopool_modbus import NeoPoolModbusClient

from homeassistant.components.modbus import async_get_unit
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_UNIT_ID, DEFAULT_UNIT_ID, DOMAIN, PLATFORMS
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .helpers import build_modbus_params
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NeoPool services."""
    async_setup_services(hass)
    return True


def _async_build_client(
    hass: HomeAssistant, entry: NeoPoolConfigEntry
) -> NeoPoolModbusClient:
    """Build the client, borrowing a shared Modbus unit from the modbus integration.

    Several integrations on one device share a single connection this way, and
    it appears in the Modbus connections panel.
    """
    try:
        unit = async_get_unit(
            hass,
            entry,
            build_modbus_params(entry.data),
            entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
        )
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        raise ConfigEntryNotReady(str(err)) from err

    return NeoPoolModbusClient(entry.data, unit=unit)


async def async_setup_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Set up the NeoPool integration from a config entry."""
    client = _async_build_client(hass, entry)
    coordinator = NeoPoolCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The first refresh ran before any entity registered its context, so
    # context-gated timer blocks were skipped; seed one more read now that
    # every context exists instead of waiting for the next scheduled poll.
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Unload a NeoPool config entry."""
    entry.runtime_data.cancel_follow_up_refresh()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
