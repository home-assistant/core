"""The Sun WEG plant coordinator integration."""

import datetime
import logging

from sunweg.api import APIHelper, LoginError, SunWegApiError
from sunweg.plant import Plant

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PLANT_ID, DOMAIN, DeviceType

SCAN_INTERVAL = datetime.timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


class SunWEGDataUpdateCoordinator(DataUpdateCoordinator[Plant]):
    """SunWEG Data Update Coordinator coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: APIHelper, plant_id: int, plant_name: str
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="SunWEG sensor",
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.plant_id = plant_id
        self.plant_name = plant_name
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, str(plant_id))},
            manufacturer="SunWEG",
            name=self.plant_name,
        )

    async def _async_update_data(self) -> Plant:
        """Fetch data from API endpoint."""
        try:
            if self.plant_id == DEFAULT_PLANT_ID:
                # this only happens at homeassistant startup, that's why ConfigEntryError is raised in this block
                plant_list = await self.hass.async_add_executor_job(self.api.listPlants)
                if len(plant_list) == 0:
                    raise ConfigEntryError(
                        translation_domain=DOMAIN,
                        translation_key="no_plants",
                    )
                self.plant_id = plant_list[0].id
                self.plant_name = plant_list[0].name

            plant = await self.hass.async_add_executor_job(
                self.api.plant, self.plant_id
            )

            if plant is None:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="plant_not_found",
                    translation_placeholders={"plant_id": str(self.plant_id)},
                )

            for inverter in plant.inverters:
                await self.hass.async_add_executor_job(
                    self.api.complete_inverter, inverter
                )
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except SunWegApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return plant

    def get_api_value(
        self,
        variable: str,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> StateType | datetime.datetime:
        """Retrieve from a Plant the desired variable value."""
        if device_type == DeviceType.TOTAL:
            return getattr(self.data, variable)

        inverter_list = [i for i in self.data.inverters if i.id == inverter_id]
        if len(inverter_list) == 0:
            return None
        inverter = inverter_list[0]

        if device_type == DeviceType.INVERTER:
            return getattr(inverter, variable)
        if device_type == DeviceType.PHASE:
            for phase in inverter.phases:
                if phase.name == deep_name:
                    return getattr(phase, variable)
        elif device_type == DeviceType.STRING:
            for mppt in inverter.mppts:
                for string in mppt.strings:
                    if string.name == deep_name:
                        return getattr(string, variable)
        return None
