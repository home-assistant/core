"""Cordinator for PTDevices integration."""

from __future__ import annotations

import logging
from typing import Final

import aioptdevices
from aioptdevices.interface import PTDevicesResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, UPDATE_INTERVAL
from .device import ptdevices_get_data

_LOGGER = logging.getLogger(__name__)
REFRESH_COOLDOWN: Final = 10


class PTDevicesCoordinator(DataUpdateCoordinator[PTDevicesResponse]):
    """Class for interacting with PTDevices get_data."""

    def __init__(self, hass: HomeAssistant, deviceId: str, authToken: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
                cooldown=REFRESH_COOLDOWN,
            ),
        )

        self._hass = hass
        self._authToken = authToken
        self._deviceId = deviceId

    async def _async_update_data(self) -> PTDevicesResponse:
        try:
            data = await ptdevices_get_data(self._hass, self._authToken, self._deviceId)

        except aioptdevices.PTDevicesRequestError as err:
            _LOGGER.warning("Failed to connect to PTDevices server")
            raise UpdateFailed(err) from err
        except aioptdevices.PTDevicesUnauthorizedError as err:
            _LOGGER.warning("Unable, to read device data because of bad token")
            raise UpdateFailed(err) from err
        except aioptdevices.PTDevicesForbiddenError as err:
            _LOGGER.warning("Unable, device does not belong to the token holder")
            raise UpdateFailed(err) from err
        else:
            return data

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo of this APC UPS, if serial number is available."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.data["body"]["id"])},
            configuration_url=f"https://www.ptdevices.com/device/level/{self.data["body"]["id"]}",
            manufacturer="ParemTech inc.",
            name=self.data["body"]["title"],
        )
