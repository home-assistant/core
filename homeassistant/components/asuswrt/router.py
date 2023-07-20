"""Represent the AsusWrt router."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .bridge import AsusWrtBridge, WrtDevice
from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_METHOD,
    KEY_SENSORS,
    SENSORS_CONNECTED_DEVICE,
)

CONF_REQ_RELOAD = [CONF_DNSMASQ, CONF_INTERFACE, CONF_REQUIRE_IP]
DEFAULT_NAME = "Asuswrt"

SCAN_INTERVAL = timedelta(seconds=30)

SENSORS_TYPE_COUNT = "sensors_count"

_LOGGER = logging.getLogger(__name__)


class AsusWrtSensorDataHandler:
    """Data handler for AsusWrt sensor."""

    def __init__(self, hass: HomeAssistant, api: AsusWrtBridge) -> None:
        """Initialize a AsusWrt sensor data handler."""
        self._hass = hass
        self._api = api
        self._connected_devices = 0

    async def _get_connected_devices(self) -> dict[str, int]:
        """Return number of connected devices."""
        return {SENSORS_CONNECTED_DEVICE[0]: self._connected_devices}

    def update_device_count(self, conn_devices: int) -> bool:
        """Update connected devices attribute."""
        if self._connected_devices == conn_devices:
            return False
        self._connected_devices = conn_devices
        return True

    async def get_coordinator(
        self,
        sensor_type: str,
        update_method: Callable[[], Any] | None = None,
    ) -> DataUpdateCoordinator:
        """Get the coordinator for a specific sensor type."""
        should_poll = True
        if sensor_type == SENSORS_TYPE_COUNT:
            should_poll = False
            method = self._get_connected_devices
        elif update_method is not None:
            method = update_method
        else:
            raise RuntimeError(f"Invalid sensor type: {sensor_type}")

        coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=sensor_type,
            update_method=method,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL if should_poll else None,
        )
        await coordinator.async_refresh()

        return coordinator


class AsusWrtDevInfo:
    """Representation of a AsusWrt device info."""

    def __init__(self, mac: str, name: str | None = None) -> None:
        """Initialize a AsusWrt device info."""
        self._mac = mac
        self._name = name
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._connected = False

    def update(self, dev_info: WrtDevice | None = None, consider_home: int = 0) -> None:
        """Update AsusWrt device info."""
        utc_point_in_time = dt_util.utcnow()
        if dev_info:
            if not self._name:
                self._name = dev_info.name or self._mac.replace(":", "_")
            self._ip_address = dev_info.ip
            self._last_activity = utc_point_in_time
            self._connected = True

        elif self._connected:
            self._connected = (
                self._last_activity is not None
                and (utc_point_in_time - self._last_activity).total_seconds()
                < consider_home
            )
            self._ip_address = None

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac(self) -> str:
        """Return device mac address."""
        return self._mac

    @property
    def name(self) -> str | None:
        """Return device name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Return device ip address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity


class AsusWrtRouter:
    """Representation of a AsusWrt router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a AsusWrt router."""
        self.hass = hass
        self._entry = entry

        self._devices: dict[str, AsusWrtDevInfo] = {}
        self._connected_devices: int = 0
        self._connect_error: bool = False

        self._sensors_data_handler: AsusWrtSensorDataHandler | None = None
        self._sensors_coordinator: dict[str, Any] = {}

        self._on_close: list[Callable] = []

        self._options: dict[str, Any] = {
            CONF_DNSMASQ: DEFAULT_DNSMASQ,
            CONF_INTERFACE: DEFAULT_INTERFACE,
            CONF_REQUIRE_IP: True,
        }
        self._options.update(entry.options)

        self._api: AsusWrtBridge = AsusWrtBridge.get_bridge(
            self.hass, dict(self._entry.data), self._options
        )

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        try:
            await self._api.async_connect()
        except OSError as exc:
            raise ConfigEntryNotReady from exc
        if not self._api.is_connected:
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        entity_reg = er.async_get(self.hass)
        track_entries = er.async_entries_for_config_entry(
            entity_reg, self._entry.entry_id
        )
        for entry in track_entries:
            if entry.domain != TRACKER_DOMAIN:
                continue
            device_mac = format_mac(entry.unique_id)

            # migrate entity unique ID if wrong formatted
            if device_mac != entry.unique_id:
                existing_entity_id = entity_reg.async_get_entity_id(
                    TRACKER_DOMAIN, DOMAIN, device_mac
                )
                if existing_entity_id:
                    # entity with uniqueid properly formatted already
                    # exists in the registry, we delete this duplicate
                    entity_reg.async_remove(entry.entity_id)
                    continue

                entity_reg.async_update_entity(
                    entry.entity_id, new_unique_id=device_mac
                )

            self._devices[device_mac] = AsusWrtDevInfo(device_mac, entry.original_name)

        # Update devices
        await self.update_devices()

        # Init Sensors
        await self.init_sensors_coordinator()

        self.async_on_close(
            async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)
        )

    async def update_all(self, now: datetime | None = None) -> None:
        """Update all AsusWrt platforms."""
        await self.update_devices()

    async def update_devices(self) -> None:
        """Update AsusWrt devices tracker."""
        new_device = False
        _LOGGER.debug("Checking devices for ASUS router %s", self.host)
        try:
            wrt_devices = await self._api.async_get_connected_devices()
        except UpdateFailed as exc:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router %s for device update: %s",
                    self.host,
                    exc,
                )
            return

        if self._connect_error:
            self._connect_error = False
            _LOGGER.info("Reconnected to ASUS router %s", self.host)

        self._connected_devices = len(wrt_devices)
        consider_home: int = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown: bool = self._options.get(
            CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN
        )

        for device_mac, device in self._devices.items():
            dev_info = wrt_devices.pop(device_mac, None)
            device.update(dev_info, consider_home)

        for device_mac, dev_info in wrt_devices.items():
            if not track_unknown and not dev_info.name:
                continue
            new_device = True
            device = AsusWrtDevInfo(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)
        await self._update_unpolled_sensors()

    async def init_sensors_coordinator(self) -> None:
        """Init AsusWrt sensors coordinators."""
        if self._sensors_data_handler:
            return

        self._sensors_data_handler = AsusWrtSensorDataHandler(self.hass, self._api)
        self._sensors_data_handler.update_device_count(self._connected_devices)

        sensors_types = await self._api.async_get_available_sensors()
        sensors_types[SENSORS_TYPE_COUNT] = {KEY_SENSORS: SENSORS_CONNECTED_DEVICE}

        for sensor_type, sensor_def in sensors_types.items():
            if not (sensor_names := sensor_def.get(KEY_SENSORS)):
                continue
            coordinator = await self._sensors_data_handler.get_coordinator(
                sensor_type, update_method=sensor_def.get(KEY_METHOD)
            )
            self._sensors_coordinator[sensor_type] = {
                KEY_COORDINATOR: coordinator,
                KEY_SENSORS: sensor_names,
            }

    async def _update_unpolled_sensors(self) -> None:
        """Request refresh for AsusWrt unpolled sensors."""
        if not self._sensors_data_handler:
            return

        if SENSORS_TYPE_COUNT in self._sensors_coordinator:
            coordinator = self._sensors_coordinator[SENSORS_TYPE_COUNT][KEY_COORDINATOR]
            if self._sensors_data_handler.update_device_count(self._connected_devices):
                await coordinator.async_refresh()

    async def close(self) -> None:
        """Close the connection."""
        if self._api is not None:
            await self._api.async_disconnect()

        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    def update_options(self, new_options: dict[str, Any]) -> bool:
        """Update router options."""
        req_reload = False
        for name, new_opt in new_options.items():
            if name in CONF_REQ_RELOAD:
                old_opt = self._options.get(name)
                if old_opt is None or old_opt != new_opt:
                    req_reload = True
                    break

        self._options.update(new_options)
        return req_reload

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id or "AsusWRT")},
            name=self.host,
            model=self._api.model or "Asus Router",
            manufacturer="Asus",
            configuration_url=f"http://{self.host}",
        )
        if self._api.firmware:
            info["sw_version"] = self._api.firmware

        return info

    @property
    def signal_device_new(self) -> str:
        """Event specific per AsusWrt entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per AsusWrt entry to signal updates in devices."""
        return f"{DOMAIN}-device-update"

    @property
    def host(self) -> str:
        """Return router hostname."""
        return self._api.host

    @property
    def unique_id(self) -> str | None:
        """Return router unique id."""
        return self._entry.unique_id

    @property
    def name(self) -> str:
        """Return router name."""
        return self.host if self.unique_id else DEFAULT_NAME

    @property
    def devices(self) -> dict[str, AsusWrtDevInfo]:
        """Return devices."""
        return self._devices

    @property
    def sensors_coordinator(self) -> dict[str, Any]:
        """Return sensors coordinators."""
        return self._sensors_coordinator
