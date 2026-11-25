"""DataUpdateCoordinator for Kingspan Watchman SENSiT."""

from datetime import timedelta
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
        self.added_tanks: set[str] = set()
        self._unavailable_tanks: set[str] = set()
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
                version=APIVersion.CONNECT_V1,
                client=self._httpx_client,
                timeout=API_TIMEOUT,
            ) as client:
                await client.login(username, password)
                tanks = await client.tanks
                results: list[TankData] = []

                for tank in tanks:
                    # Tank ID is a static parameter retrieved during login
                    tank_id = tank.serial_number
                    tank_name: str = "Unknown"
                    try:
                        tank.clear_cache()
                        tank_name = str(await tank.name)
                        raw_history = await tank.history()
                        filtered = filter_history(raw_history, usage_window)  # pyright: ignore[reportArgumentType]

                        rate = calculate_usage_rate(filtered)
                        forecast = calculate_forecast_empty(filtered, rate)

                        tank_data = TankData(
                            level=float(await tank.level),
                            serial_number=tank_id,
                            model=str(await tank.model),
                            name=tank_name,
                            capacity=float(await tank.capacity),
                            last_read=as_local(await tank.last_read),
                            history=raw_history or [],  # pyright: ignore[reportArgumentType]
                            usage_rate=rate,
                            forecast_empty=forecast,
                        )
                        if tank_id in self._unavailable_tanks:
                            _LOGGER.info(
                                "Tank '%s' data is available again",
                                tank_name,
                            )
                            self._unavailable_tanks.remove(tank_id)
                        results.append(tank_data)
                    except KingspanAPIError as err:
                        if err.code == KingspanErrorCode.NO_DATA:
                            if tank_id not in self._unavailable_tanks:
                                _LOGGER.warning(
                                    "Skipping tank '%s' (missing data): %s",
                                    tank_name,
                                    err.message,
                                )
                                self._unavailable_tanks.add(tank_id)
                            continue
                        raise

        except KingspanAPIError as err:
            if err.code == KingspanErrorCode.AUTH_FAILED:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="credentials_invalid",
                ) from err

            if err.code == KingspanErrorCode.NO_DATA:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_data",
                ) from err

            if err.code == KingspanErrorCode.TIMEOUT:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="timed_out",
                ) from err

            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

        return results
