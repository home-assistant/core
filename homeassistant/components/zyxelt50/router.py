""" The Zyxel T50 router """
""" I used these as a starting point: https://github.com/ThomasRinsma/vmg8825scripts """

from datetime import timedelta
import logging

from zyxelt50.modem import ZyxelT50Modem

from homeassistant.components.device_tracker.const import (
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class ZyxelT50Device(object):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry

        self._api: ZyxelT50Modem = None

        self._devices: dict[str, ZyxelDevice] = {}
        self._connected_devices = 0

        self._on_close = []

    async def setup(self) -> None:
        """Set up a Zyxel router."""
        self._api = await get_connection(self.hass, dict(self._entry.data))

        # Load tracked entities from registry
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entries = (
            self.hass.helpers.entity_registry.async_entries_for_config_entry(
                entity_registry, self._entry.entry_id
            )
        )
        for entry in track_entries:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = ZyxelDevice(
                    entry.unique_id, entry.original_name
                )

        # Update devices
        await self.update_devices()

        self.async_on_close(
            async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)
        )

    async def close(self) -> None:
        """Close the connection."""
        await self.hass.async_add_executor_job(self._api.logout)

        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def update_all(self, now) -> None:
        """Update all Zyxel platforms."""
        await self.update_devices()

    async def update_devices(self) -> None:
        new_device = False

        zyxel_devices = await self.hass.async_add_executor_job(
            self._api.get_connected_devices
        )
        consider_home = DEFAULT_CONSIDER_HOME.total_seconds()

        for device_mac in self._devices:
            dev_info = zyxel_devices.get(device_mac)
            self._devices[device_mac].update(dev_info, consider_home)

        for device_mac, dev_info in zyxel_devices.items():
            if device_mac in self._devices:
                continue
            new_device = True
            device = ZyxelDevice(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

        self._connected_devices = len(zyxel_devices)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Zyxel entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Zyxel entry to signal updates in devices."""
        return f"{DOMAIN}-device-update"

    @property
    def devices(self):
        """Return devices."""
        return self._devices


class ZyxelDevice:
    """Representation of a Zyxel device info."""

    def __init__(self, mac, name=None):
        """Initialize a Zyxel device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info=None, consider_home=0):
        """Update Zyxel device info."""
        utc_point_in_time = dt_util.utcnow()
        if dev_info:
            if not self._name:
                self._name = dev_info["hostName"] or self._mac.replace(":", "_")
            self._ip_address = dev_info["ipAddress"]
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


async def get_connection(hass: HomeAssistant, conf: dict) -> ZyxelT50Modem:
    """Get the AsusWrt API."""

    modem = ZyxelT50Modem(
        conf.get(CONF_PASSWORD, ""), conf[CONF_HOST], conf[CONF_USERNAME]
    )
    await hass.async_add_executor_job(modem.connect)
    return modem


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
