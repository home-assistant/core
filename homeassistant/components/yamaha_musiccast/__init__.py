"""The MusicCast integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from pyamaha import AsyncDevice, System, Zone
from .musiccast_device import MusicCastDevice
import voluptuous as vol
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    BRAND,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the MusicCast component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MusicCast from a config entry."""

    client = MusicCastDevice(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = MusicCastDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        coordinator.platforms.append(component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class MusicCastData:
    def __init__(self):
        # device info
        self.model_name = None
        self.system_version = None

        # network status
        self.mac_addresses = None
        self.network_name = None

        # features
        self.zones: Dict[str, MusicCastZoneData] = {}


class MusicCastZoneData:
    def __init__(self):
        self.power = None
        self.min_volume = 0
        self.max_volume = 100
        self.current_volume = 0


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator[MusicCastData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: MusicCastDevice) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        # the following data must not be updated frequently
        self._zone_ids = None
        self._network_status = None
        self._device_info = None
        self._features = None

        self._data: MusicCastData = MusicCastData()

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> MusicCastData:
        """Update data via library."""
        try:

            if not self._network_status:
                self._network_status = await (
                    await self.api.device.request(System.get_network_status())
                ).json()

                self._data.network_name = self._network_status.get("network_name")
                self._data.mac_addresses = self._network_status.get("mac_address")

            if not self._device_info:
                self._device_info = await (
                    await self.api.device.request(System.get_device_info())
                ).json()

                self._data.model_name = self._device_info.get("model_name")
                self._data.system_version = self._device_info.get("system_version")

            if not self._features:
                self._features = await (
                    await self.api.device.request(System.get_features())
                ).json()

                self._zone_ids = [
                    zone.get("id") for zone in self._features.get("zone", [])
                ]

                for zone in self._features.get("zone", []):
                    zone_id = zone.get("id")

                    zone_data: MusicCastZoneData = self._data.zones.get(
                        zone_id, MusicCastZoneData()
                    )

                    range_volume = next(
                        item
                        for item in zone.get("range_step")
                        if item["id"] == "volume"
                    )

                    zone_data.min_volume = range_volume.get("min")
                    zone_data.max_volume = range_volume.get("max")

                    self._data.zones[zone_id] = zone_data

            zones = {
                zone: await (
                    await self.api.device.request(Zone.get_status(zone))
                ).json()
                for zone in self._zone_ids
            }

            for zone_id in zones:
                zone = zones[zone_id]
                zone_data: MusicCastZoneData = self._data.zones.get(
                    zone_id, MusicCastZoneData()
                )

                zone_data.power = zone.get("power")
                zone_data.current_volume = zone.get("volume")

                self._data.zones[zone_id] = zone_data

            return self._data

        except Exception as exception:
            raise UpdateFailed() from exception


class MusicCastEntity(CoordinatorEntity):
    """Defines a base MusicCast entity."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: MusicCastDataUpdateCoordinator,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the MusicCast entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default


class MusicCastDeviceEntity(MusicCastEntity):
    """Defines a MusicCast device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this MusicCast device."""
        return {
            ATTR_IDENTIFIERS: {
                (
                    DOMAIN,
                    "".join(self.coordinator.data.mac_addresses.values()),
                )
            },
            ATTR_NAME: self.coordinator.data.network_name,
            ATTR_MANUFACTURER: BRAND,
            ATTR_MODEL: self.coordinator.data.model_name,
            ATTR_SOFTWARE_VERSION: self.coordinator.data.system_version,
        }
