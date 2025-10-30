"""Cordinator for PTDevices integration."""

from __future__ import annotations

import logging
from typing import Any, Final

import aioptdevices
from aioptdevices.interface import PTDevicesResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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

type PTDevicesConfigEntry = ConfigEntry[PTDevicesCoordinator]


class PTDevicesCoordinator(DataUpdateCoordinator[PTDevicesResponse]):
    """Class for interacting with PTDevices get_data."""

    config_entry: PTDevicesConfigEntry
    data: PTDevicesResponse

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PTDevicesConfigEntry,
        deviceId: str,
        authToken: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo from PTDevices."""

        device_id: str = self.data.get("body", {}).get("id", "")

        configuration_url: str = (
            f"https://www.ptdevices.com/device/level/{device_id}" if device_id else ""
        )

        return DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            configuration_url=configuration_url,
            manufacturer="ParemTech inc.",
            sw_version=self.data.get("body", {}).get("version", None),
            name=self.data.get("body", {}).get("title", ""),
        )

    async def _async_update_data(self) -> PTDevicesResponse:
        try:
            data = await ptdevices_get_data(self._hass, self._authToken, self._deviceId)

        except aioptdevices.PTDevicesRequestError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

        # Verify that we have the keys needed
        body: dict[str, Any] = data.get("body", {})
        required_keys: list[str] = ["title", "device_id", "version", "units"]
        missing_keys: list[str] = [
            required_key for required_key in required_keys if required_key not in body
        ]
        if missing_keys:
            raise UpdateFailed(
                # "Test Error {key}",
                translation_domain=DOMAIN,
                translation_key="malformed_response_missing_key",
                translation_placeholders={
                    "missing_keys": ",".join(missing_keys),
                },
            )

        return data
