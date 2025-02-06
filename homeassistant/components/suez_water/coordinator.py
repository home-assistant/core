"""Suez water update coordinator."""

from dataclasses import dataclass
from datetime import date

from pysuez import PySuezError, SuezClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_REFRESH_INTERVAL, DOMAIN


@dataclass
class SuezWaterAggregatedAttributes:
    """Class containing aggregated sensor extra attributes."""

    this_month_consumption: dict[str, float]
    previous_month_consumption: dict[str, float]
    last_year_overall: dict[str, float]
    this_year_overall: dict[str, float]
    history: dict[str, float]
    highest_monthly_consumption: float


@dataclass
class SuezWaterData:
    """Class used to hold all fetch data from suez api."""

    aggregated_value: float
    aggregated_attr: SuezWaterAggregatedAttributes
    price: float
    new_device: None | DeviceInfo
    current_device_id: str


type SuezWaterConfigEntry = ConfigEntry[SuezWaterCoordinator]


class SuezWaterCoordinator(DataUpdateCoordinator[SuezWaterData]):
    """Suez water coordinator."""

    _suez_client: SuezClient
    config_entry: SuezWaterConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SuezWaterConfigEntry) -> None:
        """Initialize suez water coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DATA_REFRESH_INTERVAL,
            always_update=True,
            config_entry=config_entry,
        )
        self.counter_id: None | str = None

    async def _async_setup(self) -> None:
        self._suez_client = SuezClient(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            counter_id=None,
        )
        if not await self._suez_client.check_credentials():
            raise ConfigEntryError("Invalid credentials for suez water")
        try:
            await self._suez_client.find_counter()
        except PySuezError as ex:
            raise ConfigEntryError("Can't find counter id") from ex

    async def _async_update_data(self) -> SuezWaterData:
        """Fetch data from API endpoint."""

        def map_dict(param: dict[date, float]) -> dict[str, float]:
            return {str(key): value for key, value in param.items()}

        try:
            new_device, counter_id = await self._get_device()
        except PySuezError as err:
            raise UpdateFailed("Suez data update failed to find counter") from err

        try:
            aggregated = await self._suez_client.fetch_aggregated_data()
            data = SuezWaterData(
                aggregated_value=aggregated.value,
                aggregated_attr=SuezWaterAggregatedAttributes(
                    this_month_consumption=map_dict(aggregated.current_month),
                    previous_month_consumption=map_dict(aggregated.previous_month),
                    highest_monthly_consumption=aggregated.highest_monthly_consumption,
                    last_year_overall=aggregated.previous_year,
                    this_year_overall=aggregated.current_year,
                    history=map_dict(aggregated.history),
                ),
                price=(await self._suez_client.get_price()).price,
                new_device=new_device,
                current_device_id=counter_id,
            )
        except PySuezError as err:
            raise UpdateFailed(f"Suez data update failed: {err}") from err
        _LOGGER.debug("Successfully fetched suez data")
        return data

    async def _get_device(self) -> tuple[None | DeviceInfo, str]:
        counter_id = str(await self._suez_client.find_counter())

        if counter_id != self.counter_id:
            if self.counter_id:
                device_registry = dr.async_get(self.hass)
                device: None | DeviceEntry = device_registry.async_get_device(
                    identifiers={(DOMAIN, self.counter_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
            self.counter_id = counter_id
            new_device = DeviceInfo(
                identifiers={(DOMAIN, counter_id)},
                entry_type=DeviceEntryType.SERVICE,
                manufacturer="Suez",
                serial_number=counter_id,
            )
        else:
            new_device = None

        return new_device, counter_id
