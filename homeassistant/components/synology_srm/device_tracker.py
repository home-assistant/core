"""Device tracker for Synology SRM routers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

import synology_srm
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DEFAULT_CONSIDER_HOME,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DOMAIN = "synology_srm"
type SynologySRMConfigEntry = ConfigEntry[SynologySrmDeviceScanner]

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

ATTRIBUTE_ALIAS = {
    "band": None,
    "connection": None,
    "current_rate": None,
    "dev_type": None,
    "hostname": None,
    "ip6_addr": None,
    "ip_addr": None,
    "is_baned": "is_banned",
    "is_beamforming_on": None,
    "is_guest": None,
    "is_high_qos": None,
    "is_low_qos": None,
    "is_manual_dev_type": None,
    "is_manual_hostname": None,
    "is_online": None,
    "is_parental_controled": "is_parental_controlled",
    "is_qos": None,
    "is_wireless": None,
    "mac": None,
    "max_rate": None,
    "mesh_node_id": None,
    "rate_quality": None,
    "signalstrength": "signal_strength",
    "transferRXRate": "transfer_rx_rate",
    "transferTXRate": "transfer_tx_rate",
}


def get_api(hass: HomeAssistant, config: dict[str, Any]) -> synology_srm:
    """Validate the configuration and return Synology SRM scanner."""

    client = synology_srm.Client(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        https=config[CONF_SSL],
    )

    if not config[CONF_VERIFY_SSL]:
        client.http.disable_https_verify()

    return client


class SynologySrmDeviceScanner:
    """Scanner to interact with Synology SRM API."""

    def __init__(self, hass: HomeAssistant, config: SynologySRMConfigEntry) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self._entry = config
        self._host = config.data[CONF_HOST]
        self.client = synology_srm.Client(
            host=config.data[CONF_HOST],
            port=config.data[CONF_PORT],
            username=config.data[CONF_USERNAME],
            password=config.data[CONF_PASSWORD],
            https=config.data[CONF_SSL],
        )

        if not config.data[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()
        self.scan_interval = timedelta(seconds=config.data[CONF_SCAN_INTERVAL])
        self.devices: list[Any] = []
        self.success_init = False
        self._on_close: list[Callable] = []

    async def setup(self) -> None:
        """Set up the scanner."""
        _LOGGER.debug("Setting up Synology SRM device scanner")
        self.success_init = await self.hass.async_add_executor_job(
            self.check_success_init
        )

        if not self.success_init:
            _LOGGER.error("Failed to connect to Synology SRM")
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        entity_reg = er.async_get(self.hass)
        track_entries = er.async_entries_for_config_entry(
            entity_reg, self._entry.entry_id
        )
        for entry in track_entries:
            if entry.domain != DOMAIN:
                continue
            self.devices.append(entry)

        self.async_on_close(
            async_track_time_interval(self.hass, self.scan_devices, self.scan_interval)
        )
        _LOGGER.debug("Synology SRM device scanner setup complete")

    async def close(self) -> None:
        """Close the connection."""
        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    def check_success_init(self) -> bool:
        """Check if the scanner was initialized successfully."""
        self.success_init = self._update_info()

        return self.success_init

    @property
    def signal_scanned_devices(self) -> str:
        """Event specific to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-scanned-devices"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"

    async def scan_devices(self, now: datetime | None = None) -> None:
        """Scan for new devices and return a list with found device IDs."""
        self.hass.async_add_executor_job(self._update_info)
        if len(self.devices) > 0:
            async_dispatcher_send(self.hass, self.signal_scanned_devices)
            async_dispatcher_send(self.hass, self.signal_device_update)
        else:
            _LOGGER.debug("No devices found connected to the router")
        _LOGGER.debug("Synology SRM device scan completed")

    def _update_info(self):
        """Check the router for connected devices."""
        _LOGGER.debug("Scanning for connected devices")

        try:
            self.devices = self.client.core.get_network_nsm_device({"is_online": True})
        except synology_srm.http.SynologyException as ex:
            _LOGGER.error("Error with the Synology SRM: %s", ex)
            return False

        _LOGGER.debug("Found %d device(s) connected to the router", len(self.devices))

        return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Synology SRM component."""
    scanner = config_entry.runtime_data
    tracked: set = set()

    @callback
    def update_devices() -> None:
        """Update scanner entities."""
        add_entities(scanner, async_add_entities, tracked)

    scanner.async_on_close(
        async_dispatcher_connect(hass, scanner.signal_scanned_devices, update_devices)
    )

    update_devices()


@callback
def add_entities(
    scanner: SynologySrmDeviceScanner,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for device in scanner.devices:
        if device["mac"] in tracked:
            continue

        new_tracked.append(SynologySRMScannerEntity(scanner, device))
        tracked.add(device["mac"])

    async_add_entities(new_tracked)


class SynologySRMScannerEntity(ScannerEntity):
    """A Synology SRM entity."""

    _attr_should_poll = False

    def __init__(
        self, scanner: SynologySrmDeviceScanner, device: dict[str, Any]
    ) -> None:
        """Init a Synology SRM device."""
        self._scanner = scanner
        self._device = device
        self._last_activity: datetime | None = None
        self._mac = format_mac(device.get("mac"))
        self._name = device.get("hostname", device.get("mac"))
        self._connected = False
        self._last_activity = None
        self._attr_source_type = SourceType.ROUTER
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @property
    def name(self) -> str | None:
        """Return device name."""
        return self._name

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._device["hostname"]

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device["ip_addr"]

    @property
    def mac_address(self) -> str | None:
        """Return a unique ID."""
        return self._mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    def icon(self) -> str:
        """Return device icon."""
        if self._device.get("is_online"):
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, str] = {}

        if not self._connected:
            return {}

        for attribute, alias in ATTRIBUTE_ALIAS.items():
            if (value := self._device.get(attribute)) is None:
                continue
            attr = alias or attribute
            attrs[attr] = value
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._scanner.signal_device_update,
                self.async_on_demand_update,
            )
        )

    @callback
    def async_on_demand_update(self) -> None:
        """Update the device information."""
        utc_point_in_time = dt_util.utcnow()
        for dev in self._scanner.devices:
            if dev["mac"] == self._mac:
                self._name = dev.get("hostname", dev.get("mac"))
                self._device = dev
                self._last_activity = utc_point_in_time
                break

        self._connected = (
            self._last_activity is not None
            and (utc_point_in_time - self._last_activity).total_seconds()
            < DEFAULT_CONSIDER_HOME.total_seconds()
        )

        if not self._connected:
            self._attr_extra_state_attributes = {}

        self.async_write_ha_state()
