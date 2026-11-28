"""Data coordinator for the dwd_weather_warnings integration."""

from typing import override

from dwdwfsapi import DwdWeatherWarningsAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.location import Coordinates
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import location as location_util

from .const import (
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .exceptions import CoordinatesNotFoundError, EntityNotFoundError
from .util import get_position_data

type DwdWeatherWarningsConfigEntry = ConfigEntry[DwdWeatherWarningsCoordinator]


class DwdWeatherWarningsCoordinator(DataUpdateCoordinator[None]):
    """Custom coordinator for the dwd_weather_warnings integration."""

    config_entry: DwdWeatherWarningsConfigEntry
    api: DwdWeatherWarningsAPI

    def __init__(
        self, hass: HomeAssistant, config_entry: DwdWeatherWarningsConfigEntry
    ) -> None:
        """Initialize the dwd_weather_warnings coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self._device_tracker: str | None = None
        self._previous_position: Coordinates | None = None

    @override
    async def _async_setup(self) -> None:
        """Set up coordinator."""
        if region_identifier := self.config_entry.data.get(CONF_REGION_IDENTIFIER):
            self.api = await self.hass.async_add_executor_job(
                DwdWeatherWarningsAPI, region_identifier
            )
        elif device_tracker := self.config_entry.data.get(CONF_REGION_DEVICE_TRACKER):
            self._device_tracker = device_tracker
            try:
                position = get_position_data(self.hass, device_tracker)
            except (EntityNotFoundError, CoordinatesNotFoundError) as err:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="position_error",
                    translation_placeholders={"entity_id": device_tracker},
                ) from err
            self.api = await self.hass.async_add_executor_job(
                DwdWeatherWarningsAPI, position
            )
            self._previous_position = position
        else:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_config",
            )

        # Finally check whether or not the initialization was successful
        if not self.api.data_valid:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )

    @override
    async def _async_update_data(self) -> None:
        """Get the latest data from the DWD Weather Warnings API."""
        if self._device_tracker:
            try:
                position = get_position_data(self.hass, self._device_tracker)
            except (EntityNotFoundError, CoordinatesNotFoundError) as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="position_error",
                    translation_placeholders={"entity_id": self._device_tracker},
                ) from err

            distance = None
            if self._previous_position is not None:
                distance = location_util.distance(
                    self._previous_position[0],
                    self._previous_position[1],
                    position[0],
                    position[1],
                )

            if distance is None or distance > 50:
                # Only create a new object on the first update
                # or when the distance to the previous position
                # changes by more than 50 meters (to take GPS
                # inaccuracy into account).
                self.api = await self.hass.async_add_executor_job(
                    DwdWeatherWarningsAPI, position
                )
            else:
                # Otherwise update the API to check for new warnings.
                await self.hass.async_add_executor_job(self.api.update)

            self._previous_position = position
        else:
            await self.hass.async_add_executor_job(self.api.update)

        # Finally check whether or not the update was successful
        if not self.api.data_valid:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
