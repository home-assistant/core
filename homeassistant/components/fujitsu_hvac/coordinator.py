"""Coordinator for Fujitsu HVAC integration."""

from asyncio import gather
from datetime import timedelta
import logging

from ayla_iot_unofficial import AylaApi, AylaAuthError
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_REFRESH_SECONDS

_LOGGER = logging.getLogger(__name__)


class FujitsuHVACCoordinator(DataUpdateCoordinator[dict[str, FujitsuHVAC]]):
    """Coordinator for Fujitsu HVAC integration."""

    def __init__(self, hass: HomeAssistant, api: AylaApi) -> None:
        """Initialize coordindtor for Fujitsu HVAC integration."""
        super().__init__(
            hass,
            _LOGGER,
            name="Fujitsu HVAC data",
            update_interval=timedelta(seconds=API_REFRESH_SECONDS),
        )
        self.api = api

    async def _async_setup(self) -> None:
        try:
            await self.api.async_sign_in()
        except TimeoutError as e:
            raise ConfigEntryNotReady(
                "Timed out while connecting to Ayla IoT API"
            ) from e
        except AylaAuthError as e:
            raise ConfigEntryAuthFailed("Credentuials expired for Ayla IoT API") from e

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

        if len(listening_entities) == 0:
            devices = list(filter(lambda x: isinstance(x, FujitsuHVAC), devices))
        else:
            devices = list(
                filter(lambda x: x.device_serial_number in listening_entities, devices)
            )

        try:
            await gather(*[dev.async_update() for dev in devices])
        except AylaAuthError as e:
            raise ConfigEntryAuthFailed("Credentials expired for Ayla IoT API") from e

        return {d.device_serial_number: d for d in devices}
