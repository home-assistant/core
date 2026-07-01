"""The Synology SRM component."""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

import synology_srm

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]

type SynologySRMConfigEntry = ConfigEntry[SynologySRMDeviceScanner]


class SynologySRMDeviceScanner:
    """Scanner to interact with Synology SRM API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: SynologySRMConfigEntry,
    ) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self._host = config.data[CONF_HOST]
        self._on_close: list[Callable] = []
        self.client = synology_srm.Client(
            host=config.data[CONF_HOST],
            port=config.data[CONF_PORT],
            username=config.data[CONF_USERNAME],
            password=config.data[CONF_PASSWORD],
            https=config.data[CONF_SSL],
        )
        if not config.data[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()
        self.scan_interval = DEFAULT_SCAN_INTERVAL
        self.devices: dict[str, dict[str, Any]] = {}

    async def setup(self) -> None:
        """Set up the scanner."""
        _LOGGER.debug("Setting up Synology SRM device scanner")

        await self.hass.async_add_executor_job(self._check_success_init)

        self.async_on_close(
            async_track_time_interval(self.hass, self.scan_devices, self.scan_interval)
        )

        await self.scan_devices()
        _LOGGER.debug("Synology SRM device scanner setup complete")

    async def close(self) -> None:
        """Close the connection."""
        for func in self._on_close:
            func()
        self._on_close.clear()

    async def scan_devices(self, now: datetime | None = None) -> None:
        """Refresh the cached list of devices from the router."""
        await self._update_info()

    def _check_success_init(self) -> None:
        """Probe the SRM. Raises an entry-state exception on failure."""
        try:
            self.client.core.get_network_nsm_device({"is_online": True})
        except (
            synology_srm.http.SynologyApiError,
            synology_srm.http.SynologyHttpException,
        ) as ex:
            raise ConfigEntryAuthFailed from ex
        except synology_srm.http.SynologyException as ex:
            raise ConfigEntryNotReady from ex

    async def _update_info(self) -> None:
        """Check the router for connected devices."""
        _LOGGER.debug("Scanning for connected devices")
        new_devices = False
        try:
            srm_devices = await self.hass.async_add_executor_job(
                self.client.core.get_network_nsm_device, {"is_online": True}
            )
            for device in srm_devices:
                device_mac = format_mac(device["mac"])
                if device_mac not in self.devices:
                    new_devices = True
                    _LOGGER.debug("Found new device: %s", device_mac)
                device["last_activity"] = dt_util.utcnow()
                self.devices[device_mac] = device

            if new_devices:
                _LOGGER.debug("New devices found, updating entities")
                async_dispatcher_send(self.hass, self.signal_device_new)

            async_dispatcher_send(self.hass, self.signal_device_update)

        except synology_srm.http.SynologyException as ex:
            _LOGGER.error("Error with the Synology SRM: %s", ex)

        _LOGGER.debug("Found %d device(s) connected to the router", len(self.devices))

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when synology srm is closed."""
        self._on_close.append(func)

    @property
    def signal_device_new(self) -> str:
        """Event specific per entry to signal new device."""
        return f"{DOMAIN}-{self._host}-scanned-devices"

    @property
    def signal_device_update(self) -> str:
        """Event specific per entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SynologySRMConfigEntry
) -> bool:
    """Set up the Synology SRM from a config entry."""
    scanner = SynologySRMDeviceScanner(hass, config_entry)
    await scanner.setup()

    async def async_close_connection(event: Event) -> None:
        """Close Synology SRM on HA Stop."""
        await scanner.close()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    config_entry.async_on_unload(scanner.close)

    config_entry.runtime_data = scanner

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: SynologySRMConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
