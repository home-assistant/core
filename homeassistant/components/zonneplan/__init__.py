"""The Zonneplan integration."""

from pyzonneplan import Token, Zonneplan
from pyzonneplan.const import ContractType

from homeassistant.const import CONF_EMAIL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    ZonneplanBatteryControlCoordinator,
    ZonneplanBatteryCoordinator,
    ZonneplanBatterySettingsCoordinator,
    ZonneplanChargePointCoordinator,
    ZonneplanConfigEntry,
    ZonneplanCoordinator,
    ZonneplanRuntimeData,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> None:
    """Set up Zonneplan from a config entry."""
    zonneplan = Zonneplan(
        email=entry.data[CONF_EMAIL],
        session=async_get_clientsession(hass),
        token=Token.from_dict(entry.data[CONF_TOKEN]),
    )
    coordinator = ZonneplanCoordinator(hass, entry, zonneplan)
    await coordinator.async_config_entry_first_refresh()

    battery_connection_uuids = {
        contract.uuid: connection.uuid
        for connection in coordinator.data.account.connections
        for contract in connection.contracts_of_type(ContractType.HOME_BATTERY)
    }
    battery_coordinator = ZonneplanBatteryCoordinator(
        hass, entry, zonneplan, battery_connection_uuids
    )
    await battery_coordinator.async_config_entry_first_refresh()
    battery_control_coordinator = ZonneplanBatteryControlCoordinator(
        hass, entry, zonneplan, battery_connection_uuids
    )
    # Not a first refresh: a failing control mode must not take down the sensors.
    await battery_control_coordinator.async_refresh()
    battery_settings_coordinator = ZonneplanBatterySettingsCoordinator(
        hass, entry, zonneplan, battery_control_coordinator
    )
    await battery_settings_coordinator.async_refresh()

    charge_point_coordinator = ZonneplanChargePointCoordinator(
        hass,
        entry,
        zonneplan,
        {
            contract.uuid: connection.uuid
            for connection in coordinator.data.account.connections
            for contract in connection.contracts_of_type(ContractType.CHARGE_POINT)
        },
    )
    await charge_point_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ZonneplanRuntimeData(
        coordinator=coordinator,
        battery_coordinator=battery_coordinator,
        battery_control_coordinator=battery_control_coordinator,
        charge_point_coordinator=charge_point_coordinator,
        battery_settings_coordinator=battery_settings_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
