"""The MusicCast integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiomusiccast import MusicCastConnectionException
from aiomusiccast.musiccast_device import MusicCastData, MusicCastDevice

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import BRAND, CONF_SERIAL, CONF_UPNP_DESC, DOMAIN

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def get_upnp_desc(hass: HomeAssistant, host: str):
    """Get the upnp description URL for a given host, using the SSPD scanner."""
    ssdp_entries = await ssdp.async_get_discovery_info_by_st(hass, "upnp:rootdevice")
    matches = [w for w in ssdp_entries if w.get("_host", "") == host]
    upnp_desc = None
    for match in matches:
        if match.get(ssdp.ATTR_SSDP_LOCATION):
            upnp_desc = match[ssdp.ATTR_SSDP_LOCATION]
            break

    if not upnp_desc:
        _LOGGER.warning(
            "The upnp_description was not found automatically, setting a default one"
        )
        upnp_desc = f"http://{host}:49154/MediaRenderer/desc.xml"
    return upnp_desc


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MusicCast from a config entry."""

    if entry.data.get(CONF_UPNP_DESC) is None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: entry.data[CONF_HOST],
                CONF_SERIAL: entry.data["serial"],
                CONF_UPNP_DESC: await get_upnp_desc(hass, entry.data[CONF_HOST]),
            },
        )

    client = MusicCastDevice(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
        entry.data[CONF_UPNP_DESC],
    )
    coordinator = MusicCastDataUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator[MusicCastData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: MusicCastDevice) -> None:
        """Initialize."""
        self.musiccast = client

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.entities: list[MusicCastDeviceEntity] = []

    async def _async_update_data(self) -> MusicCastData:
        """Update data via library."""
        try:
            await self.musiccast.fetch()
        except MusicCastConnectionException as exception:
            raise UpdateFailed() from exception
        return self.musiccast.data


class MusicCastEntity(CoordinatorEntity):
    """Defines a base MusicCast entity."""

    coordinator: MusicCastDataUpdateCoordinator

    def __init__(
        self,
        *,
        name: str,
        icon: str,
        coordinator: MusicCastDataUpdateCoordinator,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the MusicCast entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name

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
    def device_info(self) -> DeviceInfo:
        """Return device information about this MusicCast device."""
        return DeviceInfo(
            connections={
                (CONNECTION_NETWORK_MAC, format_mac(mac))
                for mac in self.coordinator.data.mac_addresses.values()
            },
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.data.device_id,
                )
            },
            name=self.coordinator.data.network_name,
            manufacturer=BRAND,
            model=self.coordinator.data.model_name,
            sw_version=self.coordinator.data.system_version,
        )
