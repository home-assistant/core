"""Represent the GLinet router."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Callable

from gli_py import GLinet
from gli_py.error_handling import NonZeroResponse, TokenError

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_PASSWORD
from homeassistant.core import (  # callback,CALLBACK_TYPE
    CALLBACK_TYPE,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.event import async_track_time_interval

# from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

# from typing import Any


# from homeassistant.helpers.event import async_track_time_interval


_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


class ClientDevInfo:
    """Representation of a device connected to the router."""

    def __init__(self, mac: str, name=None):
        """Initialize a connected device."""
        self._mac: str = mac
        self._name: str | None = name
        self._ip_address: str | None = None
        self._last_activity: datetime = dt_util.utcnow() - timedelta(days=1)
        self._connected: bool = False

    def update(self, dev_info: dict = None, consider_home=0):
        """Update connected device info."""
        # TODO actually cause this function to run by configuring some devices to track
        now: datetime = dt_util.utcnow()
        if dev_info:
            if not self._name:
                pass  # TODO access device name - GLinet usus '*' if unknown
                if dev_info["name"] == "*":
                    self._name = self._mac.replace(":", "_")
                else:
                    self._name = dev_info["name"]
            self._ip_address = dev_info["ip"]
            self._last_activity = now
            self._connected = dev_info["online"]

        # a device might not actually be online but we want to consider it home
        elif self._connected:
            self._connected = (
                now - self._last_activity
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


class GLinetRouter:
    """representation of a GLinet router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a GLinet router."""
        self.hass: HomeAssistant = hass
        self._entry: ConfigEntry = entry

        self._api: GLinet = None
        self._host: str = entry.data[CONF_HOST]
        # self._model = "GL-inet router"
        # self._sw_v = None
        self._connect_error: bool = False
        self._token_error: bool = False
        # self._devices should
        self._devices: dict[str, ClientDevInfo] = {}
        self._connected_devices: int = 0
        self._on_close: list[Callable] = []

        self._options: dict = {}
        self._options.update(entry.options)

    async def setup(self) -> None:
        """Set up a GL-inet router."""

        try:
            self._api = get_api(self._entry.data)
            # self._devices = await self._api.list_all_clients() #DELETEME
            # self._connected_devices = await self._api.connected_clients()
        except OSError as exc:
            _LOGGER.error(
                "Error connecting to GL-inet router %s for setup: %s",
                self._host,
                exc,
            )
            raise ConfigEntryNotReady from exc

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entries: list[
            RegistryEntry
        ] = self.hass.helpers.entity_registry.async_entries_for_config_entry(
            entity_registry, self._entry.entry_id
        )

        for entry in track_entries:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = ClientDevInfo(
                    entry.unique_id, entry.original_name
                )

        # Update devices
        await self.update_devices()

        self.async_on_close(
            async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)
        )

    async def renew_token(self):
        """Attempt to get a new token."""
        try:
            await self._api.async_login(self._entry.data[CONF_PASSWORD])
            self._entry.data[CONF_API_TOKEN] = self._api.token
            _LOGGER.warning(
                "GL-inet router %s token was renewed",
                self._host,
            )
        except Exception as exc:
            _LOGGER.error(
                "GL-inet %s failed to renew the token, have you changed your router password?: %s",
                self._host,
                exc,
            )

    async def update_all(self, now: datetime | None = None) -> None:
        """Update all Gli-net platforms."""
        await self.update_devices()

    async def update_devices(self) -> None:
        """Update Gl-inet devices tracker."""
        new_device = False

        _LOGGER.debug("Checking client connect to GL-inet router %s", self._host)
        try:
            if self._token_error:
                await self.renew_token()
            wrt_devices = await self._api.async_connected_clients()
        except TimeoutError as exc:
            if not self._connect_error:
                self._connect_error = True
            _LOGGER.error(
                "GL-inet router %s did not respond in time: %s",
                self._host,
                exc,
            )
            return
        except TokenError as exc:
            self._token_error = True
            if not self._connect_error:
                self._connect_error = True
            _LOGGER.warning(
                "GL-inet router %s token was refused %s, will try to re-autheticate before next poll",
                self._host,
                exc,
            )
            return
        except NonZeroResponse as exc:
            if not self._connect_error:
                self._connect_error = True
            _LOGGER.error(
                "GL-inet router %s responded, but with an error code: %s",
                self._host,
                exc,
            )
            return
        except Exception as exc:
            if not self._connect_error:
                self._connect_error = True
            _LOGGER.error(
                "GL-inet router %s responded with an unexpected error: %s",
                self._host,
                exc,
            )
            return
        if self._token_error:
            self._token_error = False
            _LOGGER.info("Gl-inet %s token is now renewed", self._host)

        if self._connect_error:
            self._connect_error = False
            _LOGGER.info("Reconnected to Gl-inet router %s", self._host)

        consider_home = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        # track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        # TODO - ensure the output of gli_py devices has the correct data structure
        for device_mac, device in self._devices.items():
            dev_info = wrt_devices.get(device_mac)
            device.update(dev_info, consider_home)

        for device_mac, dev_info in wrt_devices.items():
            if device_mac in self._devices:
                continue
            if not dev_info["name"]:
                continue
            new_device = True
            device = ClientDevInfo(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

        self._connected_devices = len(wrt_devices)

    def update_options(self, new_options: dict) -> bool:
        """Update router options."""
        req_reload = False
        self._options.update(new_options)
        return req_reload

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, "GL-inet")},
            "name": self._host,
            # "model": self._model,
            "manufacturer": "GL-inet",
            # "sw_version": self._sw_v,
        }

    @property
    def signal_device_new(self) -> str:
        """Event specific per GL-inet entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per GL-inet entry to signal updates in devices."""
        return f"{DOMAIN}-device-update"

    @property
    def host(self) -> str:
        """Return router host."""
        return self._host

    @property
    def devices(self) -> dict[str, ClientDevInfo]:
        """Return devices."""
        return self._devices

    @property
    def api(self) -> GLinet:
        """Return router API."""
        return self._api


def get_api(conf) -> GLinet:
    """Get the GLinet API."""
    if CONF_API_TOKEN in conf:
        return GLinet(
            sync=False,
            token=conf[CONF_API_TOKEN],
            base_url=conf[CONF_HOST] + "/cgi-bin/api/",
        )
    if CONF_PASSWORD in conf:
        router = GLinet(sync=False, base_url=conf[CONF_HOST] + "/cgi-bin/api/")
        # this is synchronous code, ergh
        router.login(conf[CONF_PASSWORD])
        return router
    else:
        _LOGGER.error(
            "Error setting up GL-inet router, no auth details found in configuration"
        )
        raise ConfigEntryAuthFailed
