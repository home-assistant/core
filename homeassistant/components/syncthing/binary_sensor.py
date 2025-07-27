"""Support for monitoring Syncthing device connectivity."""

import aiosyncthing

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SCAN_INTERVAL, SERVER_AVAILABLE, SERVER_UNAVAILABLE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Syncthing device connectivity binary sensors."""
    syncthing = hass.data[DOMAIN][config_entry.entry_id]

    try:
        version = await syncthing.system.version()
        connections = await syncthing.system.connections()
    except aiosyncthing.exceptions.SyncthingError as exception:
        raise PlatformNotReady from exception

    server_id = syncthing.server_id

    entities = [
        DeviceConnectivityBinarySensor(
            syncthing,
            server_id,
            device_id,
            device_info.get("address", "Unknown"),
            version["version"],
        )
        for device_id, device_info in connections.get("connections", {}).items()
    ]

    async_add_entities(entities)


class DeviceConnectivityBinarySensor(BinarySensorEntity):
    """A Syncthing device connectivity binary sensor."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, syncthing, server_id, device_id, address, version):
        """Initialize the binary sensor."""
        self._syncthing = syncthing
        self._server_id = server_id
        self._device_id = device_id
        self._address = address
        self._connected = None
        self._unsub_timer = None

        self._short_server_id = server_id.split("-")[0]
        self._attr_name = f"{self._short_server_id} Device {device_id}"
        self._attr_unique_id = f"{self._short_server_id}-device-{device_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._server_id)},
            manufacturer="Syncthing Team",
            name=f"Syncthing ({syncthing.url})",
            sw_version=version,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(self._connected)

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._connected is not None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "device_id": self._device_id,
            "address": self._address,
        }

    async def async_update_status(self):
        """Request device connection status and update state."""
        try:
            connections = await self._syncthing.system.connections()
            device_info = connections["connections"].get(self._device_id, {})
            self._connected = device_info.get("connected", False)
        except aiosyncthing.exceptions.SyncthingError:
            self._connected = None
        self.async_write_ha_state()

    def subscribe(self):
        """Request device status and update state."""
        if self._unsub_timer is None:

            async def refresh(event_time):
                await self.async_update_status()

            self._unsub_timer = async_track_time_interval(
                self.hass, refresh, SCAN_INTERVAL
            )

    @callback
    def unsubscribe(self):
        """Stop polling syncthing device status."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        @callback
        def handle_server_unavailable():
            self._connected = None
            self.unsubscribe()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._server_id}",
                handle_server_unavailable,
            )
        )

        async def handle_server_available():
            self.subscribe()
            await self.async_update_status()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_AVAILABLE}-{self._server_id}",
                handle_server_available,
            )
        )

        self.subscribe()
        self.async_on_remove(self.unsubscribe)
        await self.async_update_status()
