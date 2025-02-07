"""Coordinator for Fujitsu HVAC integration."""

import logging

from ayla_iot_unofficial import AylaApi, AylaAuthError
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_REFRESH

_LOGGER = logging.getLogger(__name__)


class FGLairCoordinator(DataUpdateCoordinator[dict[str, FujitsuHVAC]]):
    """Coordinator for Fujitsu HVAC integration."""

    def __init__(self, hass: HomeAssistant, api: AylaApi) -> None:
        """Initialize coordinator for Fujitsu HVAC integration."""
        super().__init__(
            hass,
            _LOGGER,
            name="Fujitsu HVAC data",
            update_interval=API_REFRESH,
        )
        self.api = api

    async def _async_setup(self) -> None:
        try:
            await self.api.async_sign_in()
        except AylaAuthError as e:
            raise ConfigEntryAuthFailed("Credentials expired for Ayla IoT API") from e

    async def _async_update_data(self) -> dict[str, FujitsuHVAC]:
        """Fetch data from api endpoint."""
        listening_entities = set(self.async_contexts())
        try:
            if self.api.token_expired:
                await self.api.async_sign_in()

            if self.api.token_expiring_soon:
                await self.api.async_refresh_auth()

            devices = await self.api.async_get_devices()
        except AylaAuthError as e:
            raise ConfigEntryAuthFailed("Credentials expired for Ayla IoT API") from e

        if not listening_entities:
            devices = [
                dev
                for dev in devices
                if isinstance(dev, FujitsuHVAC) and dev.is_online()
            ]
        else:
            devices = [
                dev
                for dev in devices
                if dev.device_serial_number in listening_entities and dev.is_online()
            ]

        try:
            for dev in devices:
                await dev.async_update()
        except AylaAuthError as e:
            raise ConfigEntryAuthFailed("Credentials expired for Ayla IoT API") from e

        return {d.device_serial_number: d for d in devices}
