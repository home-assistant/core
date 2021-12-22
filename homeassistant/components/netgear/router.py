"""Represent the Netgear router and its devices."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_NAME,
    DOMAIN,
    MODELS_V2,
)
from .errors import CannotLoginException

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


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


@callback
def async_setup_netgear_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_class_generator: Callable[[NetgearRouter, dict], list],
) -> None:
    """Set up device tracker for Netgear component."""
    router = hass.data[DOMAIN][entry.unique_id]
    tracked = set()

    @callback
    def _async_router_updated():
        """Update the values of the router."""
        async_add_new_entities(
            router, async_add_entities, tracked, entity_class_generator
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, _async_router_updated)
    )

    _async_router_updated()


@callback
def async_add_new_entities(router, async_add_entities, tracked, entity_class_generator):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.extend(entity_class_generator(router, device))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked, True)


class NetgearRouter:
    """Representation of a Netgear router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a Netgear router."""
        self.hass = hass
        self.entry = entry
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

        self.method_version = 1
        consider_home_int = entry.options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        self._consider_home = timedelta(seconds=consider_home_int)

        self._api: Netgear = None
        self._attrs = {}

        self.devices = {}

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
        self.device_name = self._info.get("DeviceName", DEFAULT_NAME)
        self.model = self._info.get("ModelName")
        self.firmware_version = self._info.get("Firmwareversion")

        for model in MODELS_V2:
            if self.model.startswith(model):
                self.method_version = 2

    async def async_setup(self) -> None:
        """Set up a Netgear router."""
        await self.hass.async_add_executor_job(self._setup)

        # set already known devices to away instead of unavailable
        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(device_registry, self.entry_id)
        for device_entry in devices:
            if device_entry.via_device_id is None:
                continue  # do not add the router itself

            device_mac = dict(device_entry.connections).get(dr.CONNECTION_NETWORK_MAC)
            self.devices[device_mac] = {
                "mac": device_mac,
                "name": device_entry.name,
                "active": False,
                "last_seen": dt_util.utcnow() - timedelta(days=365),
                "device_model": None,
                "device_type": None,
                "type": None,
                "link_rate": None,
                "signal": None,
                "ip": None,
                "ssid": None,
                "conn_ap_mac": None,
            }

        await self.async_update_device_trackers()
        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass, self.async_update_device_trackers, SCAN_INTERVAL
            )
        )

        async_dispatcher_send(self.hass, self.signal_device_new)

    async def async_get_attached_devices(self) -> list:
        """Get the devices connected to the router."""
        if self.method_version == 1:
            return await self.hass.async_add_executor_job(
                self._api.get_attached_devices
            )

        return await self.hass.async_add_executor_job(self._api.get_attached_devices_2)

    async def async_update_device_trackers(self, now=None) -> None:
        """Update Netgear devices."""
        new_device = False
        ntg_devices = await self.async_get_attached_devices()
        now = dt_util.utcnow()

        if ntg_devices is None:
            return

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Netgear scan result: \n%s", ntg_devices)

        for ntg_device in ntg_devices:
            device_mac = format_mac(ntg_device.mac)

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


class NetgearDeviceEntity(Entity):
    """Base class for a device connected to a Netgear router."""

    def __init__(self, router: NetgearRouter, device: dict) -> None:
        """Initialize a Netgear device."""
        self._router = router
        self._device = device
        self._mac = device["mac"]
        self._name = self.get_device_name()
        self._device_name = self._name
        self._unique_id = self._mac
        self._active = device["active"]

    def get_device_name(self):
        """Return the name of the given device or the MAC if we don't know."""
        name = self._device["name"]
        if not name or name == "--":
            name = self._mac

        return name

    @abstractmethod
    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            default_name=self._device_name,
            default_model=self._device["device_model"],
            via_device=(DOMAIN, self._router.unique_id),
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_update_device,
            )
        )
