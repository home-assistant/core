"""DataUpdateCoordinator for Kingspan Watchman SENSiT."""

from datetime import timedelta
import inspect
import logging
from typing import override

from connectsensor.analysis import (
    TankData,
    calculate_forecast_empty,
    calculate_usage_rate,
    filter_history,
)
from connectsensor.client import APIVersion, AsyncSensorClient
from connectsensor.exceptions import KingspanAPIError, KingspanErrorCode
import httpx2

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import as_local

from .const import (
    API_TIMEOUT,
    CONF_USAGE_WINDOW,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_USAGE_WINDOW,
    DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("AsyncSensorClient loaded from %s", inspect.getfile(AsyncSensorClient))

type SENSiTConfigEntry = ConfigEntry[SENSiTDataUpdateCoordinator]  # pylint: disable=invalid-name


class SENSiTDataUpdateCoordinator(DataUpdateCoordinator[list[TankData]]):
    """Class to manage fetching data from the API."""

    config_entry: SENSiTConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SENSiTConfigEntry,
        httpx_client: httpx2.AsyncClient,
    ) -> None:
        """Initialize."""
        self._httpx_client = httpx_client
        self._unavailable_logged = False
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_UPDATE_INTERVAL),
            config_entry=config_entry,
        )

    @override
    async def _async_update_data(self) -> list[TankData]:
        """Update data via API."""
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]
        usage_window = self.config_entry.options.get(
            CONF_USAGE_WINDOW, DEFAULT_USAGE_WINDOW
        )

        try:
            async with AsyncSensorClient(
                version=APIVersion.KNECT_V1,
                client=self._httpx_client,
                timeout=API_TIMEOUT,
            ) as client:
                await client.login(username, password)
                tanks = await client.tanks
                results: list[TankData] = []

                for tank in tanks:
                    tank.clear_cache()
                    raw_history = await tank.history()
                    filtered = filter_history(raw_history, usage_window)  # pyright: ignore[reportArgumentType]

                    rate = calculate_usage_rate(filtered)
                    forecast = calculate_forecast_empty(filtered, rate)

                    tank_data = TankData(
                        level=float(await tank.level),
                        serial_number=str(await tank.serial_number),
                        model=str(await tank.model),
                        name=str(await tank.name),
                        capacity=float(await tank.capacity),
                        last_read=as_local(await tank.last_read),
                        history=raw_history or [],  # pyright: ignore[reportArgumentType]
                        usage_rate=rate,
                        forecast_empty=forecast,
                    )
                    results.append(tank_data)

        except KingspanAPIError as err:
            if err.code == KingspanErrorCode.AUTH_FAILED:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="credentials_invalid",
                ) from err

            if err.code == KingspanErrorCode.NO_DATA:
                _LOGGER.warning("No data available for username '%s'", username)
                return []

            if not self._unavailable_logged:
                _LOGGER.warning(
                    "Error communicating with Kingspan API: %s", err.message
                )
                self._unavailable_logged = True

            if err.code == KingspanErrorCode.TIMEOUT:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="timed_out",
                ) from err

            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"message": err.message},
            ) from err

        if self._unavailable_logged:
            _LOGGER.info("Kingspan service is available again")
            self._unavailable_logged = False

        return results
