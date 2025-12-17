"""Coordinator for PTDevices integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Final

import aioptdevices
from aioptdevices.interface import Interface, PTDevicesResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REFRESH_COOLDOWN: Final = 30
UPDATE_INTERVAL = timedelta(seconds=60)

type PTDevicesConfigEntry = ConfigEntry[PTDevicesCoordinator]


class PTDevicesCoordinator(DataUpdateCoordinator[PTDevicesResponse]):
    """Class for interacting with PTDevices get_data."""

    config_entry: PTDevicesConfigEntry
    data: PTDevicesResponse

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PTDevicesConfigEntry,
        ptdevices_interface: Interface,
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

        self.interface = ptdevices_interface

    async def _async_update_data(self) -> PTDevicesResponse:
        try:
            async with timeout(10):
                data: PTDevicesResponse = await self.interface.get_data()
        except aioptdevices.PTDevicesRequestError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_access_token",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

        # Verify that we have all keys required
        body = data["body"]
        required_keys: list[str] = [
            "title",
            "device_id",
            "version",
            "units",
            "user_name",
        ]
        for device in body.values():
            missing_keys: list[str] = [
                required_key
                for required_key in required_keys
                if required_key not in device
            ]
            if missing_keys:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="malformed_response_missing_key",
                    translation_placeholders={
                        "missing_keys": ",".join(missing_keys),
                    },
                )

        return data
