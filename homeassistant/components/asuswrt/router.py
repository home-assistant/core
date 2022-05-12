"""Represent the AsusWrt router."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from aioasuswrt.asuswrt import AsusWrt, Device as WrtDevice

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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
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
    SENSORS_BYTES,
    SENSORS_CONNECTED_DEVICE,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
)

CONF_REQ_RELOAD = [CONF_DNSMASQ, CONF_INTERFACE, CONF_REQUIRE_IP]
DEFAULT_NAME = "Asuswrt"

KEY_COORDINATOR = "coordinator"
KEY_SENSORS = "sensors"

SCAN_INTERVAL = timedelta(seconds=30)

SENSORS_TYPE_BYTES = "sensors_bytes"
SENSORS_TYPE_COUNT = "sensors_count"
SENSORS_TYPE_LOAD_AVG = "sensors_load_avg"
SENSORS_TYPE_RATES = "sensors_rates"
SENSORS_TYPE_TEMPERATURES = "sensors_temperatures"

_LOGGER = logging.getLogger(__name__)


def _get_dict(keys: list, values: list) -> dict[str, Any]:
    """Create a dict from a list of keys and values."""
    ret_dict: dict[str, Any] = dict.fromkeys(keys)

    for index, key in enumerate(ret_dict):
        ret_dict[key] = values[index]

    return ret_dict


class AsusWrtSensorDataHandler:
    """Data handler for AsusWrt sensor."""

    def __init__(self, hass: HomeAssistant, api: AsusWrt) -> None:
        """Initialize a AsusWrt sensor data handler."""
        self._hass = hass
        self._api = api
        self._connected_devices = 0

    async def _get_connected_devices(self) -> dict[str, int]:
        """Return number of connected devices."""
        return {SENSORS_CONNECTED_DEVICE[0]: self._connected_devices}

    async def _get_bytes(self) -> dict[str, Any]:
        """Fetch byte information from the router."""
        try:
            datas = await self._api.async_get_bytes_total()
        except (OSError, ValueError) as exc:
            raise UpdateFailed(exc) from exc

        return _get_dict(SENSORS_BYTES, datas)

    async def _get_rates(self) -> dict[str, Any]:
        """Fetch rates information from the router."""
        try:
            rates = await self._api.async_get_current_transfer_rates()
        except (OSError, ValueError) as exc:
            raise UpdateFailed(exc) from exc

        return _get_dict(SENSORS_RATES, rates)

    async def _get_load_avg(self) -> dict[str, Any]:
        """Fetch load average information from the router."""
        try:
            avg = await self._api.async_get_loadavg()
        except (OSError, ValueError) as exc:
            raise UpdateFailed(exc) from exc

        return _get_dict(SENSORS_LOAD_AVG, avg)

    async def _get_temperatures(self) -> dict[str, Any]:
        """Fetch temperatures information from the router."""
        try:
            temperatures: dict[str, Any] = await self._api.async_get_temperature()
        except (OSError, ValueError) as exc:
            raise UpdateFailed(exc) from exc

        return temperatures

    def update_device_count(self, conn_devices: int) -> bool:
        """Update connected devices attribute."""
        if self._connected_devices == conn_devices:
            return False
        self._connected_devices = conn_devices
        return True

    async def get_coordinator(
        self, sensor_type: str, should_poll: bool = True
    ) -> DataUpdateCoordinator:
        """Get the coordinator for a specific sensor type."""
        if sensor_type == SENSORS_TYPE_COUNT:
            method = self._get_connected_devices
        elif sensor_type == SENSORS_TYPE_BYTES:
            method = self._get_bytes
        elif sensor_type == SENSORS_TYPE_LOAD_AVG:
            method = self._get_load_avg
        elif sensor_type == SENSORS_TYPE_RATES:
            method = self._get_rates
        elif sensor_type == SENSORS_TYPE_TEMPERATURES:
            method = self._get_temperatures
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

        self._api: AsusWrt = None
        self._protocol: str = entry.data[CONF_PROTOCOL]
        self._host: str = entry.data[CONF_HOST]
        self._model: str = "Asus Router"
        self._sw_v: str | None = None

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

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        self._api = get_api(dict(self._entry.data), self._options)

        try:
            await self._api.connection.async_connect()
        except OSError as exp:
            raise ConfigEntryNotReady from exp

        if not self._api.is_connected:
            raise ConfigEntryNotReady

        # System
        model = await get_nvram_info(self._api, "MODEL")
        if model and "model" in model:
            self._model = model["model"]
        firmware = await get_nvram_info(self._api, "FIRMWARE")
        if firmware and "firmver" in firmware and "buildno" in firmware:
            self._sw_v = f"{firmware['firmver']} (build {firmware['buildno']})"

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
        _LOGGER.debug("Checking devices for ASUS router %s", self._host)
        try:
            api_devices = await self._api.async_get_connected_devices()
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

        self._connected_devices = len(api_devices)
        consider_home: int = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown: bool = self._options.get(
            CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN
        )

        wrt_devices = {format_mac(mac): dev for mac, dev in api_devices.items()}
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

        sensors_types: dict[str, list[str]] = {
            SENSORS_TYPE_BYTES: SENSORS_BYTES,
            SENSORS_TYPE_COUNT: SENSORS_CONNECTED_DEVICE,
            SENSORS_TYPE_LOAD_AVG: SENSORS_LOAD_AVG,
            SENSORS_TYPE_RATES: SENSORS_RATES,
            SENSORS_TYPE_TEMPERATURES: await self._get_available_temperature_sensors(),
        }

        for sensor_type, sensor_names in sensors_types.items():
            if not sensor_names:
                continue
            coordinator = await self._sensors_data_handler.get_coordinator(
                sensor_type, sensor_type != SENSORS_TYPE_COUNT
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

    async def _get_available_temperature_sensors(self) -> list[str]:
        """Check which temperature information is available on the router."""
        try:
            availability = await self._api.async_find_temperature_commands()
            available_sensors = [
                SENSORS_TEMPERATURES[i] for i in range(3) if availability[i]
            ]
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Failed checking temperature sensor availability for ASUS router %s. Exception: %s",
                self._host,
                exc,
            )
            return []

        return available_sensors

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
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id or "AsusWRT")},
            name=self._host,
            model=self._model,
            manufacturer="Asus",
            sw_version=self._sw_v,
            configuration_url=f"http://{self._host}",
        )

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
    def unique_id(self) -> str | None:
        """Return router unique id."""
        return self._entry.unique_id

    @property
    def name(self) -> str:
        """Return router name."""
        return self._host if self.unique_id else DEFAULT_NAME

    @property
    def devices(self) -> dict[str, AsusWrtDevInfo]:
        """Return devices."""
        return self._devices

    @property
    def sensors_coordinator(self) -> dict[str, Any]:
        """Return sensors coordinators."""
        return self._sensors_coordinator


async def get_nvram_info(api: AsusWrt, info_type: str) -> dict[str, Any]:
    """Get AsusWrt router info from nvram."""
    info = {}
    try:
        info = await api.async_get_nvram(info_type)
    except OSError as exc:
        _LOGGER.warning("Error calling method async_get_nvram(%s): %s", info_type, exc)

    return info


def get_api(conf: dict[str, Any], options: dict[str, Any] | None = None) -> AsusWrt:
    """Get the AsusWrt API."""
    opt = options or {}

    return AsusWrt(
        conf[CONF_HOST],
        conf.get(CONF_PORT),
        conf[CONF_PROTOCOL] == PROTOCOL_TELNET,
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        opt.get(CONF_REQUIRE_IP, True),
        interface=opt.get(CONF_INTERFACE, DEFAULT_INTERFACE),
        dnsmasq=opt.get(CONF_DNSMASQ, DEFAULT_DNSMASQ),
    )
