"""Represent the AsusWrt router."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    PROTOCOL_TELNET,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)

CONF_REQ_RELOAD = [CONF_DNSMASQ, CONF_INTERFACE, CONF_REQUIRE_IP]

KEY_COORDINATOR = "coordinator"
KEY_SENSORS = "sensors"

SCAN_INTERVAL = timedelta(seconds=30)

SENSORS_TYPE_BYTES = "sensors_bytes"
SENSORS_TYPE_COUNT = "sensors_count"
SENSORS_TYPE_RATES = "sensors_rates"

_LOGGER = logging.getLogger(__name__)


class AsusWrtSensorDataHandler:
    """Data handler for AsusWrt sensor."""

    def __init__(self, hass, api):
        """Initialize a AsusWrt sensor data handler."""
        self._hass = hass
        self._api = api
        self._connected_devices = 0

    async def _get_connected_devices(self):
        """Return number of connected devices."""
        return {SENSOR_CONNECTED_DEVICE: self._connected_devices}

    async def _get_bytes(self):
        """Fetch byte information from the router."""
        ret_dict: dict[str, Any] = {}
        try:
            datas = await self._api.async_get_bytes_total()
        except OSError as exc:
            raise UpdateFailed from exc

        ret_dict[SENSOR_RX_BYTES] = datas[0]
        ret_dict[SENSOR_TX_BYTES] = datas[1]

        return ret_dict

    async def _get_rates(self):
        """Fetch rates information from the router."""
        ret_dict: dict[str, Any] = {}
        try:
            rates = await self._api.async_get_current_transfer_rates()
        except OSError as exc:
            raise UpdateFailed from exc

        ret_dict[SENSOR_RX_RATES] = rates[0]
        ret_dict[SENSOR_TX_RATES] = rates[1]

        return ret_dict

    def update_device_count(self, conn_devices: int):
        """Update connected devices attribute."""
        if self._connected_devices == conn_devices:
            return False
        self._connected_devices = conn_devices
        return True

    async def get_coordinator(self, sensor_type: str, should_poll=True):
        """Get the coordinator for a specific sensor type."""
        if sensor_type == SENSORS_TYPE_COUNT:
            method = self._get_connected_devices
        elif sensor_type == SENSORS_TYPE_BYTES:
            method = self._get_bytes
        elif sensor_type == SENSORS_TYPE_RATES:
            method = self._get_rates
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

    def __init__(self, mac, name=None):
        """Initialize a AsusWrt device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info=None, consider_home=0):
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
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
            self._ip_address = None

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac(self):
        """Return device mac address."""
        return self._mac

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def ip_address(self):
        """Return device ip address."""
        return self._ip_address

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity


class AsusWrtRouter:
    """Representation of a AsusWrt router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a AsusWrt router."""
        self.hass = hass
        self._entry = entry

        self._api: AsusWrt = None
        self._protocol = entry.data[CONF_PROTOCOL]
        self._host = entry.data[CONF_HOST]

        self._devices: dict[str, Any] = {}
        self._connected_devices = 0
        self._connect_error = False

        self._sensors_data_handler: AsusWrtSensorDataHandler = None
        self._sensors_coordinator: dict[str, Any] = {}

        self._on_close = []

        self._options = {
            CONF_DNSMASQ: DEFAULT_DNSMASQ,
            CONF_INTERFACE: DEFAULT_INTERFACE,
            CONF_REQUIRE_IP: True,
        }
        self._options.update(entry.options)

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        self._api = get_api(self._entry.data, self._options)

        try:
            await self._api.connection.async_connect()
        except OSError as exp:
            raise ConfigEntryNotReady from exp

        if not self._api.is_connected:
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entries = (
            self.hass.helpers.entity_registry.async_entries_for_config_entry(
                entity_registry, self._entry.entry_id
            )
        )
        for entry in track_entries:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = AsusWrtDevInfo(
                    entry.unique_id, entry.original_name
                )

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
        _LOGGER.debug("Checking devices for ASUS router %s", self._host)
        try:
            wrt_devices = await self._api.async_get_connected_devices()
        except OSError as exc:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router %s for device update: %s",
                    self._host,
                    exc,
                )
            return

        if self._connect_error:
            self._connect_error = False
            _LOGGER.info("Reconnected to ASUS router %s", self._host)

        consider_home = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        for device_mac in self._devices:
            dev_info = wrt_devices.get(device_mac)
            self._devices[device_mac].update(dev_info, consider_home)

        for device_mac, dev_info in wrt_devices.items():
            if device_mac in self._devices:
                continue
            if not track_unknown and not dev_info.name:
                continue
            new_device = True
            device = AsusWrtDevInfo(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

        self._connected_devices = len(wrt_devices)
        await self._update_unpolled_sensors()

    async def init_sensors_coordinator(self) -> None:
        """Init AsusWrt sensors coordinators."""
        if self._sensors_data_handler:
            return

        self._sensors_data_handler = AsusWrtSensorDataHandler(self.hass, self._api)
        self._sensors_data_handler.update_device_count(self._connected_devices)

        conn_dev_coordinator = await self._sensors_data_handler.get_coordinator(
            SENSORS_TYPE_COUNT, False
        )
        self._sensors_coordinator[SENSORS_TYPE_COUNT] = {
            KEY_COORDINATOR: conn_dev_coordinator,
            KEY_SENSORS: [SENSOR_CONNECTED_DEVICE],
        }

        bytes_coordinator = await self._sensors_data_handler.get_coordinator(
            SENSORS_TYPE_BYTES
        )
        self._sensors_coordinator[SENSORS_TYPE_BYTES] = {
            KEY_COORDINATOR: bytes_coordinator,
            KEY_SENSORS: [SENSOR_RX_BYTES, SENSOR_TX_BYTES],
        }

        rates_coordinator = await self._sensors_data_handler.get_coordinator(
            SENSORS_TYPE_RATES
        )
        self._sensors_coordinator[SENSORS_TYPE_RATES] = {
            KEY_COORDINATOR: rates_coordinator,
            KEY_SENSORS: [SENSOR_RX_RATES, SENSOR_TX_RATES],
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
        if self._api is not None and self._protocol == PROTOCOL_TELNET:
            self._api.connection.disconnect()
        self._api = None

        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    def update_options(self, new_options: dict) -> bool:
        """Update router options."""
        req_reload = False
        for name, new_opt in new_options.items():
            if name in (CONF_REQ_RELOAD):
                old_opt = self._options.get(name)
                if not old_opt or old_opt != new_opt:
                    req_reload = True
                    break

        self._options.update(new_options)
        return req_reload

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, "AsusWRT")},
            "name": self._host,
            "model": "Asus Router",
            "manufacturer": "Asus",
        }

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
        return self._host

    @property
    def devices(self) -> dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def sensors_coordinator(self) -> dict[str, Any]:
        """Return sensors coordinators."""
        return self._sensors_coordinator

    @property
    def api(self) -> AsusWrt:
        """Return router API."""
        return self._api


def get_api(conf: dict, options: dict | None = None) -> AsusWrt:
    """Get the AsusWrt API."""
    opt = options or {}

    return AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == PROTOCOL_TELNET,
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        opt.get(CONF_REQUIRE_IP, True),
        interface=opt.get(CONF_INTERFACE, DEFAULT_INTERFACE),
        dnsmasq=opt.get(CONF_DNSMASQ, DEFAULT_DNSMASQ),
    )
