"""Get status for all stations for InCharge."""
from __future__ import annotations

import datetime
import logging

import async_timeout
from incharge.api import InCharge
import requests

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)

SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="total_energy_consumption",
        name="Total Energy Consumption",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the InCharge sensor."""
    # Add entities for each charging station
    incharge_data_coordinator = hass.data[DOMAIN][config_entry.entry_id]
    response = await hass.async_add_executor_job(
        incharge_data_coordinator.incharge_api.get_stations
    )
    for station in response.json()["stations"]:
        entities = [
            InChargeEntity(
                coordinator=incharge_data_coordinator,
                station_id=station["name"],
                unique_id=f"{station['name']}-{description.name}",
                description=description,
            )
            for description in SENSOR_TYPES
        ]
        async_add_entities(entities, update_before_add=True)


class InChargeEntity(CoordinatorEntity, SensorEntity):
    """Representation of a InCharge Sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: InChargeDataCoordinator,
        station_id: str,
        unique_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a InCharge sensor."""
        super().__init__(coordinator, context=station_id)
        self.coordinator = coordinator
        self.station_id = station_id
        self.entity_description = description
        self._attr_name = f"{station_id} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:ev-station"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            manufacturer="InCharge",
            name=station_id,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        result = self.coordinator.data[self.station_id][self.entity_description.key]
        return result


class InChargeDataCoordinator(DataUpdateCoordinator):
    """The class for handling data retrieval."""

    def __init__(self, hass: HomeAssistant, incharge_api: InCharge) -> None:
        """Initialize the InCharge data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="InCharge DC",
            update_interval=datetime.timedelta(minutes=5),
        )
        self.incharge_api = incharge_api

    async def _async_update_data(self):
        """Fetch data from InCharge API endpoint."""
        try:
            async with async_timeout.timeout(10):
                response = await self.hass.async_add_executor_job(
                    self.incharge_api.get_stations
                )
                response.raise_for_status()
                station_ids = [
                    station["name"] for station in response.json().get("stations")
                ]
                results: dict[str, dict] = {}
                for station_id in station_ids:
                    response = await self.hass.async_add_executor_job(
                        self.incharge_api.get_station_consumption, station_id
                    )
                    results[station_id] = {
                        "total_energy_consumption": response.json()[0]["total"]
                    }
                return results

        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
