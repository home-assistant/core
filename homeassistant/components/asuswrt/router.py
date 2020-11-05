"""Represent the AsusWrt router and its devices and sensors."""
from aioasuswrt.asuswrt import AsusWrt
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_TRACK_NEW,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_TRACK_NEW,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    DOMAIN,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


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
        if dev_info:
            self._name = dev_info.name
            self._ip_address = dev_info.ip
            self._last_activity = utcnow()
            self._connected = True

        elif self._connected:
            self._connected = (
                utcnow() - self._last_activity
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

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a AsusWrt router."""
        self.hass = hass
        self._entry = entry

        self._api: AsusWrt = None
        self._host = entry.data[CONF_HOST]
        self._name = entry.data.get(CONF_NAME, self._host)
        self._model = None
        self._sw_v = None

        self._devices: Dict[str, Any] = {}
        self._connected_devices = 0
        self._connect_error = False

        self.sensors_temperature: Dict[str, int] = {}
        self.sensors_connection: Dict[str, float] = {}

        self._unsub_dispatcher = None
        self.options = entry.options.copy()
        self.listeners = []

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        self._api = get_api(self._entry.data)

        try:
            await self._api.connection.async_connect()
            if not self._api.is_connected:
                raise ConfigEntryNotReady
        except OSError as exp:
            raise ConfigEntryNotReady from exp

        # System
        model = await self._get_nvram_info("MODEL")
        if model:
            self._model = model["model"]
        firmware = await self._get_nvram_info("FIRMWARE")
        if firmware:
            self._sw_v = f"{firmware['firmver']} (build {firmware['buildno']})"

        # Load tracked entities from registry
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entities = (
            self.hass.helpers.entity_registry.async_entries_for_config_entry(
                entity_registry, self._entry.entry_id
            )
        )
        for entry in track_entities:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = AsusWrtDevInfo(
                    entry.unique_id, entry.original_name
                )

        # Devices & sensors
        await self.update_all()

        # add options update listener
        self.listeners.append(self._entry.add_update_listener(update_listener))

        self._unsub_dispatcher = async_track_time_interval(
            self.hass, self.update_all, SCAN_INTERVAL
        )

    async def _get_nvram_info(self, info_type):
        """Get info from nvram AsusWrt router."""
        info = {}
        try:
            info = await self._api.async_get_nvram(info_type)
        except OSError:
            pass

        return info

    async def update_all(self, now: Optional[datetime] = None) -> None:
        """Update all AsusWrt platforms."""
        await self.update_devices()
        await self.update_sensors()

    async def update_devices(self) -> None:
        """Update AsusWrt devices tracker."""
        new_device = False
        _LOGGER.debug("Checking Devices")
        try:
            wrt_devices = await self._api.async_get_connected_devices()
            if self._connect_error:
                self._connect_error = False
                _LOGGER.info("Reconnected to ASUS router")

        except OSError as err:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router for device update: %s", err
                )
            return

        self._connected_devices = len(wrt_devices)

        consider_home = self.options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_new = self.options.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)

        for device_mac in self._devices:
            dev_info = wrt_devices.get(device_mac)
            self._devices[device_mac].update(dev_info, consider_home)

        if track_new:
            for device_mac, dev_info in wrt_devices.items():
                if self._devices.get(device_mac):
                    continue
                new_device = True
                device = AsusWrtDevInfo(device_mac)
                device.update(dev_info)
                self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def update_sensors(self) -> None:
        """Update AsusWrt sensors."""
        # System sensors
        try:
            datas = await self._api.async_get_bytes_total()
            rates = await self._api.async_get_current_transfer_rates()
            if self._connect_error:
                self._connect_error = False
                _LOGGER.info("Reconnected to ASUS router")

        except OSError as err:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router for sensor update: %s", err
                )
            return

        self.sensors_connection[SENSOR_CONNECTED_DEVICE] = self._connected_devices
        self.sensors_connection[SENSOR_RX_BYTES] = datas[0]
        self.sensors_connection[SENSOR_TX_BYTES] = datas[1]
        self.sensors_connection[SENSOR_RX_RATES] = rates[0]
        self.sensors_connection[SENSOR_TX_RATES] = rates[1]

        # Temperature sensors
        # try:
        #    temperatures = await self._api.async_get_temperature()
        #    self.sensors_temperature = temperatures
        # except OSError:
        #    pass

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def close(self) -> None:
        """Close the connection."""
        if self._api is not None:
            if hasattr(self._api.connection, "disconnect"):
                await self._api.connection.disconnect()
            self._unsub_dispatcher()
        self._api = None

        for listener in self.listeners:
            listener()
        self.listeners.clear()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": self._name,
            "model": self._model,
            "manufacturer": "Asus",
            "sw_version": self._sw_v,
        }

    @property
    def signal_device_new(self) -> str:
        """Event specific per AsusWrt entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per AsusWrt entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per AsusWrt entry to signal updates in sensors."""
        return f"{DOMAIN}-{self._host}-sensor-update"

    @property
    def host(self) -> str:
        """Return devices."""
        return self._host

    @property
    def devices(self) -> Dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def sensors(self) -> Dict[str, Any]:
        """Return sensors."""
        return {**self.sensors_temperature, **self.sensors_connection}


def get_api(conf: Dict) -> AsusWrt:
    """Get the AsusWrt API."""

    return AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == "telnet",
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        conf[CONF_REQUIRE_IP],
        interface=conf[CONF_INTERFACE],
        dnsmasq=conf[CONF_DNSMASQ],
    )


async def update_listener(hass: HomeAssistantType, entry: ConfigEntry):
    """Update when config_entry options update."""
    router = hass.data[DOMAIN][entry.unique_id]
    router.options = entry.options.copy()
