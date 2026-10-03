"""The SteamVR Base Station integration."""

from typing import TYPE_CHECKING

from lighthouse_ble import BaseStationV2, LighthouseError

from homeassistant.components.bluetooth import (
    BluetoothReachabilityIntent,
    async_address_reachability_diagnostics,
    async_ble_device_from_address,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SteamVRBaseStationConfigEntry, SteamVRBaseStationCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(
    hass: HomeAssistant, entry: SteamVRBaseStationConfigEntry
) -> bool:
    """Set up a base station from a config entry."""
    if TYPE_CHECKING:
        assert entry.unique_id is not None

    ble_device = async_ble_device_from_address(hass, entry.unique_id, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "name": entry.title,
                "reason": async_address_reachability_diagnostics(
                    hass, entry.unique_id, BluetoothReachabilityIntent.CONNECTION
                ),
            },
        )
    station = BaseStationV2(ble_device)
    try:
        device_info = await station.read_device_info()
    except LighthouseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"name": entry.title},
        ) from err
    coordinator = SteamVRBaseStationCoordinator(hass, entry, station, device_info)
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_start())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SteamVRBaseStationConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
