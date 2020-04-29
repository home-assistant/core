"""Represent the Netgear router and its devices."""
from datetime import timedelta
import logging
from typing import Dict

from pynetgear import Netgear

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class NetgearRouter:
    """Representation of a Netgear router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a Netgear router."""
        self.hass = hass
        self._host = entry.data.get(CONF_HOST)
        self._port = entry.data.get(CONF_PORT)
        self._ssl = entry.data.get(CONF_SSL)
        self._username = entry.data.get(CONF_USERNAME)
        self._password = entry.data[CONF_PASSWORD]
        self._tracked_devices = entry.data.get(CONF_DEVICES)
        self._excluded_devices = entry.data.get(CONF_EXCLUDE)

        self._api: Netgear = None
        self._attrs = {}

        self.devices: Dict[str, any] = {}

        self._unsub_dispatcher = None
        self.listeners = []

    async def setup(self) -> None:
        """Set up a Netgear router."""
        self._api = await self.hass.async_add_executor_job(
            Netgear, self._password, self._host, self._username, self._port, self._ssl
        )

        try:
            await self.hass.async_add_executor_job(self._api.login)
        except OSError:
            _LOGGER.exception("Failed to connect to Netgear")
            return ConfigEntryNotReady

        await self.update_devices()
        self._unsub_dispatcher = async_track_time_interval(
            self.hass, self.update_devices, SCAN_INTERVAL
        )

    def unload(self) -> None:
        """Unload a Netgear router."""
        self._unsub_dispatcher()
        self._unsub_dispatcher = None

    async def update_devices(self, now=None) -> None:
        """Update Netgear devices."""
        new_device = False
        ntg_devices: Dict[str, any] = await self.hass.async_add_executor_job(
            self._api.get_attached_devices_2
        )

        for device in self.devices.values():
            device["active"] = False

        for ntg_device in ntg_devices:
            device_mac = ntg_device.mac

            if not ntg_device.link_rate:
                continue

            tracked = (
                not self._tracked_devices
                or ntg_device.mac in self._tracked_devices
                or ntg_device.name in self._tracked_devices
            )
            tracked = tracked and (
                not self._excluded_devices
                or not (
                    ntg_device.mac in self._excluded_devices
                    or ntg_device.name in self._excluded_devices
                )
            )

            if not tracked:
                continue

            if not self.devices.get(device_mac):
                new_device = True

            self.devices[device_mac] = ntg_device._asdict()
            self.devices[device_mac]["active"] = True
            _LOGGER.warning(self.devices[device_mac])

        async_dispatcher_send(self.hass, self.signal_device_update)

        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Netgear entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Netgear entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"
