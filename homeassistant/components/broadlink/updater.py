"""Support for fetching data from Broadlink devices."""
from abc import ABC, abstractmethod
from datetime import timedelta
from functools import partial
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    CommandNotSupportedError,
    StorageError,
)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import debounce
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import CONF_LOCK, DOMAIN
from .helpers import get_ip_or_none

_LOGGER = logging.getLogger(__name__)


def get_update_manager(device):
    """Return an update manager for a given Broadlink device."""
    if device.api.model.startswith("RM mini"):
        return BroadlinkRMMini3UpdateManager(device)

    update_managers = {
        "A1": BroadlinkA1UpdateManager,
        "BG1": BroadlinkBG1UpdateManager,
        "MP1": BroadlinkMP1UpdateManager,
        "RM2": BroadlinkRMUpdateManager,
        "RM4": BroadlinkRMUpdateManager,
        "SP1": BroadlinkSP1UpdateManager,
        "SP2": BroadlinkSP2UpdateManager,
        "SP4": BroadlinkSP4UpdateManager,
        "SP4B": BroadlinkSP4UpdateManager,
    }
    return update_managers[device.api.type](device)


class BroadlinkScout:
    """Manages device discovery."""

    def __init__(self, hass):
        """Initialize the scout."""
        self.hass = hass
        self.timeout = 5
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="discovery",
            update_method=self.async_discover,
            update_interval=timedelta(minutes=15),
            request_refresh_debouncer=debounce.Debouncer(
                hass, _LOGGER, cooldown=self.timeout, immediate=True
            ),
        )
        self.coordinator.async_add_listener(self.update_listener)

    @callback
    def update_listener(self):
        """Create config flows for the devices discovered."""
        devices = self.coordinator.data
        if not (self.coordinator.last_update_success and devices):
            return

        entries = self.hass.config_entries.async_entries(DOMAIN)
        hosts_and_macs = {
            (get_ip_or_none(entry.data[CONF_HOST]), entry.data[CONF_MAC])
            for entry in entries
        }
        for device in devices:
            host, mac_addr = device.host[0], device.mac.hex()
            if (host, mac_addr) in hosts_and_macs:
                continue

            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        CONF_HOST: device.host[0],
                        CONF_MAC: device.mac.hex(),
                        CONF_TYPE: device.devtype,
                        CONF_NAME: device.name,
                        CONF_LOCK: device.is_locked,
                    },
                )
            )

    async def async_discover(self):
        """Discover Broadlink devices available on the local network."""
        try:
            discover = partial(blk.discover, timeout=self.timeout)
            devices = await self.hass.async_add_executor_job(discover)

        except OSError as err:
            raise UpdateFailed(err) from err

        return devices


class BroadlinkUpdateManager(ABC):
    """Representation of a Broadlink update manager.

    Implement this class to manage fetching data from the device and to
    monitor device availability.
    """

    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, device):
        """Initialize the update manager."""
        self.device = device
        self.coordinator = DataUpdateCoordinator(
            device.hass,
            _LOGGER,
            name=f"{device.name} ({device.api.model} at {device.api.host[0]})",
            update_method=self.async_update,
            update_interval=self.SCAN_INTERVAL,
        )
        self.available = None
        self.last_update = None

    async def async_update(self):
        """Fetch data from the device and update availability."""
        try:
            data = await self.async_fetch_data()

        except (BroadlinkException, OSError) as err:
            if self.available and (
                dt.utcnow() - self.last_update > self.SCAN_INTERVAL * 3
                or isinstance(err, (AuthorizationError, OSError))
            ):
                self.available = False
                _LOGGER.warning(
                    "Disconnected from %s (%s at %s)",
                    self.device.name,
                    self.device.api.model,
                    self.device.api.host[0],
                )
                discovery = self.device.hass.data[DOMAIN].discovery
                await discovery.coordinator.async_request_refresh()
            raise UpdateFailed(err) from err

        else:
            if self.available is False:
                _LOGGER.warning(
                    "Connected to %s (%s at %s)",
                    self.device.name,
                    self.device.api.model,
                    self.device.api.host[0],
                )
            self.available = True
            self.last_update = dt.utcnow()
            return data

    @abstractmethod
    async def async_fetch_data(self):
        """Fetch data from the device."""


class BroadlinkA1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink A1 devices."""

    SCAN_INTERVAL = timedelta(seconds=10)

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors_raw)


class BroadlinkMP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink MP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_power)


class BroadlinkRMMini3UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink RM mini 3 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        await self.device.async_request(self.device.api.hello)
        return {}


class BroadlinkRMUpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink RM2 and RM4 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors)


class BroadlinkSP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return None


class BroadlinkSP2UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP2 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        data = {}
        data["state"] = await self.device.async_request(self.device.api.check_power)
        try:
            data["load_power"] = await self.device.async_request(
                self.device.api.get_energy
            )
        except (CommandNotSupportedError, StorageError):
            data["load_power"] = None
        return data


class BroadlinkBG1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink BG1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)


class BroadlinkSP4UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP4 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)
