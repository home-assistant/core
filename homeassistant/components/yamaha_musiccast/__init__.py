"""The MusicCast integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiomusiccast import MusicCastConnectionException
from aiomusiccast.capabilities import Capability
from aiomusiccast.musiccast_device import MusicCastData, MusicCastDevice

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS, ATTR_VIA_DEVICE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BRAND,
    CONF_SERIAL,
    CONF_UPNP_DESC,
    DEFAULT_ZONE,
    DOMAIN,
    ENTITY_CATEGORY_MAPPING,
)

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def get_upnp_desc(hass: HomeAssistant, host: str):
    """Get the upnp description URL for a given host, using the SSPD scanner."""
    ssdp_entries = await ssdp.async_get_discovery_info_by_st(hass, "upnp:rootdevice")
    matches = [w for w in ssdp_entries if w.ssdp_headers.get("_host", "") == host]
    upnp_desc = None
    for match in matches:
        if upnp_desc := match.ssdp_location:
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
    coordinator.musiccast.build_capabilities()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.musiccast.device.enable_polling()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id].musiccast.device.disable_polling()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator[MusicCastData]):  # pylint: disable=hass-enforce-coordinator-module
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


class MusicCastEntity(CoordinatorEntity[MusicCastDataUpdateCoordinator]):
    """Defines a base MusicCast entity."""

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
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_icon = icon
        self._attr_name = name


class MusicCastDeviceEntity(MusicCastEntity):
    """Defines a MusicCast device entity."""

    _zone_id: str = DEFAULT_ZONE

    @property
    def device_id(self):
        """Return the ID of the current device."""
        if self._zone_id == DEFAULT_ZONE:
            return self.coordinator.data.device_id
        return f"{self.coordinator.data.device_id}_{self._zone_id}"

    @property
    def device_name(self):
        """Return the name of the current device."""
        return self.coordinator.data.zones[self._zone_id].name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this MusicCast device."""

        device_info = DeviceInfo(
            name=self.device_name,
            identifiers={
                (
                    DOMAIN,
                    self.device_id,
                )
            },
            manufacturer=BRAND,
            model=self.coordinator.data.model_name,
            sw_version=self.coordinator.data.system_version,
        )

        if self._zone_id == DEFAULT_ZONE:
            device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
                for mac in self.coordinator.data.mac_addresses.values()
            }
        else:
            device_info[ATTR_VIA_DEVICE] = (DOMAIN, self.coordinator.data.device_id)

        return device_info

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # All entities should register callbacks to update HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)


class MusicCastCapabilityEntity(MusicCastDeviceEntity):
    """Base Entity type for all capabilities."""

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        capability: Capability,
        zone_id: str | None = None,
    ) -> None:
        """Initialize a capability based entity."""
        if zone_id is not None:
            self._zone_id = zone_id
        self.capability = capability
        super().__init__(name=capability.name, icon="", coordinator=coordinator)
        self._attr_entity_category = ENTITY_CATEGORY_MAPPING.get(capability.entity_type)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.device_id}_{self.capability.id}"
