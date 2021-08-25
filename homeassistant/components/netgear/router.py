"""Represent the Netgear router and its devices."""
from datetime import timedelta
import logging

from pynetgear import Netgear

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    CONF_TRACKED_LIST,
    DEFAULT_CONSIDER_HOME,
    DOMAIN,
    MODELS_V2,
)
from .errors import CannotLoginException

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


def convert_tracked_list(tracked_list_str):
    """Convert tracked list string to a list."""
    tracked_list = []
    tracked_list_unformatted = []

    # remove '[' and ']' chars
    tracked_list_str = tracked_list_str.replace("]", "").replace("[", "")

    if tracked_list_str:
        tracked_list_unformatted = cv.ensure_list_csv(tracked_list_str)

    for mac in tracked_list_unformatted:
        tracked_list.append(format_mac(mac))

    return tracked_list


def get_api(
    password: str,
    host: str = None,
    username: str = None,
    port: int = None,
    ssl: bool = False,
) -> Netgear:
    """Get the Netgear API and login to it."""
    api: Netgear = Netgear(password, host, username, port, ssl)

    if not api.login():
        raise CannotLoginException

    return api


class NetgearRouter:
    """Representation of a Netgear router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a Netgear router."""
        self.hass = hass
        self.entry_id = entry.entry_id
        self.unique_id = entry.unique_id
        self._host = entry.data.get(CONF_HOST)
        self._port = entry.data.get(CONF_PORT)
        self._ssl = entry.data.get(CONF_SSL)
        self._username = entry.data.get(CONF_USERNAME)
        self._password = entry.data[CONF_PASSWORD]

        self._info = None
        self.model = None
        self.device_name = None
        self.firmware_version = None

        self._method_version = 1
        consider_home_int = entry.options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        self._tracked_list = convert_tracked_list(
            entry.options.get(CONF_TRACKED_LIST, "")
        )
        self._consider_home = timedelta(seconds=consider_home_int)

        self._api: Netgear = None
        self._attrs = {}

        self.devices = {}

        self._unsub_dispatcher = None

    def _setup(self) -> None:
        """Set up a Netgear router sync portion."""
        self._api = get_api(
            self._password,
            self._host,
            self._username,
            self._port,
            self._ssl,
        )

        self._info = self._api.get_info()
        self.device_name = self._info["DeviceName"]
        self.model = self._info["ModelName"]
        self.firmware_version = self._info["Firmwareversion"]

        if self.model in MODELS_V2:
            self._method_version = 2

    async def async_setup(self) -> None:
        """Set up a Netgear router."""
        await self.hass.async_add_executor_job(self._setup)

        # set already known devices to away instead of unavailable
        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(entity_registry, self.entry_id)
        for entity_entry in entries:
            self.devices[entity_entry.unique_id] = {
                "mac": entity_entry.unique_id,
                "name": entity_entry.original_name,
                "active": False,
                "last_seen": dt_util.utcnow() - timedelta(days=365),
                "device_model": None,
                "device_type": None,
                "type": None,
                "link_rate": None,
                "signal": None,
                "ip": None,
            }

        await self.async_update_device_trackers()
        self._unsub_dispatcher = async_track_time_interval(
            self.hass, self.async_update_device_trackers, SCAN_INTERVAL
        )

        async_dispatcher_send(self.hass, self.signal_device_new)

    async def async_unload(self) -> None:
        """Unload a Netgear router."""
        self._unsub_dispatcher()
        self._unsub_dispatcher = None

    async def async_get_attached_devices(self) -> None:
        """Get the devices connected to the router."""
        if self._method_version == 1:
            return await self.hass.async_add_executor_job(
                self._api.get_attached_devices
            )

        return await self.hass.async_add_executor_job(self._api.get_attached_devices_2)

    async def async_update_device_trackers(self, now=None) -> None:
        """Update Netgear devices."""
        new_device = False
        ntg_devices = await self.async_get_attached_devices()
        now = dt_util.utcnow()

        for ntg_device in ntg_devices:
            device_mac = format_mac(ntg_device.mac)

            if self._method_version == 2 and not ntg_device.link_rate:
                continue

            if self._tracked_list and device_mac not in self._tracked_list:
                continue

            if not self.devices.get(device_mac):
                new_device = True

            # ntg_device is a namedtuple from the collections module that needs conversion to a dict through ._asdict method
            self.devices[device_mac] = ntg_device._asdict()
            self.devices[device_mac]["mac"] = device_mac
            self.devices[device_mac]["last_seen"] = now

        for device in self.devices.values():
            device["active"] = now - device["last_seen"] <= self._consider_home

        async_dispatcher_send(self.hass, self.signal_device_update)

        if new_device:
            _LOGGER.debug("Netgear tracker: new device found")
            async_dispatcher_send(self.hass, self.signal_device_new)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Netgear entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Netgear entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"
