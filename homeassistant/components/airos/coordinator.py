"""DataUpdateCoordinator for AirOS."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, TypeVar

from airos.airos6 import AirOS6, AirOS6Data
from airos.airos8 import AirOS8, AirOS8Data
from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
)
from airos.helpers import DetectDeviceData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL, UPDATE_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type AirOSDeviceDetect = AirOS8 | AirOS6
type AirOSDataDetect = AirOS8Data | AirOS6Data
type AirOSUpdateData = dict[str, Any]

type AirOSConfigEntry = ConfigEntry[AirOSRuntimeData]

T = TypeVar("T", bound=AirOSDataDetect | AirOSUpdateData)


@dataclass
class AirOSRuntimeData:
    """Data for AirOS config entry."""

    status: AirOSDataUpdateCoordinator
    firmware: AirOSFirmwareUpdateCoordinator | None


async def async_fetch_airos_data(
    airos_device: AirOSDeviceDetect,
    update_method: Callable[[], Awaitable[T]],
) -> T:
    """Fetch data from AirOS device."""
    try:
        await airos_device.login()
        return await update_method()
    except AirOSConnectionAuthenticationError as err:
        _LOGGER.exception("Error authenticating with airOS device")
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except (
        AirOSConnectionSetupError,
        AirOSDeviceConnectionError,
        TimeoutError,
    ) as err:
        _LOGGER.error("Error connecting to airOS device: %s", err)
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except AirOSDataMissingError as err:
        _LOGGER.error("Expected data not returned by airOS device: %s", err)
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="error_data_missing",
        ) from err


class AirOSDataUpdateCoordinator(DataUpdateCoordinator[AirOSDataDetect]):
    """Class to manage fetching AirOS status data from single endpoint."""

    config_entry: AirOSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirOSConfigEntry,
        device_data: DetectDeviceData,
        airos_device: AirOSDeviceDetect,
    ) -> None:
        """Initialize the coordinator."""
        self.airos_device = airos_device
        self.device_data = device_data
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> AirOSDataDetect:
        """Fetch status data from AirOS."""
        return await async_fetch_airos_data(self.airos_device, self.airos_device.status)


class AirOSFirmwareUpdateCoordinator(DataUpdateCoordinator[AirOSUpdateData]):
    """Class to manage fetching AirOS firmware."""

    config_entry: AirOSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirOSConfigEntry,
        airos_device: AirOSDeviceDetect,
    ) -> None:
        """Initialize the coordinator."""
        self.airos_device = airos_device
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> AirOSUpdateData:
        """Fetch firmware data from AirOS."""
        return await async_fetch_airos_data(
            self.airos_device, self.airos_device.update_check
        )
