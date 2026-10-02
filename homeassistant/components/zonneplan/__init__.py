"""The Zonneplan integration."""

from pyzonneplan import Token, Zonneplan
from pyzonneplan.const import ContractType

from homeassistant.const import CONF_EMAIL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    ZonneplanBatteryCoordinator,
    ZonneplanConfigEntry,
    ZonneplanCoordinator,
    ZonneplanRuntimeData,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> bool:
    """Set up Zonneplan from a config entry."""
    zonneplan = Zonneplan(
        email=entry.data[CONF_EMAIL],
        session=async_get_clientsession(hass),
        token=Token.from_dict(entry.data[CONF_TOKEN]),
    )
    coordinator = ZonneplanCoordinator(hass, entry, zonneplan)
    await coordinator.async_config_entry_first_refresh()

    battery_coordinator = ZonneplanBatteryCoordinator(
        hass,
        entry,
        zonneplan,
        {
            contract.uuid: connection.uuid
            for connection in coordinator.data.account.connections
            for contract in connection.contracts_of_type(ContractType.HOME_BATTERY)
        },
    )
    await battery_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ZonneplanRuntimeData(
        coordinator=coordinator, battery_coordinator=battery_coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
