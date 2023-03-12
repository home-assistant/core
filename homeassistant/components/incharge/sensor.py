"""Get status for all stations for InCharge."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from incharge.api import InCharge
import requests

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "total_energy_consumption": SensorEntityDescription(
        key="total_energy_consumption",
        name="Total Energy Consumption",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the InCharge sensor."""
    config = {**config_entry.data}
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    incharge_api = InCharge(username, password)
    try:
        response = await hass.async_add_executor_job(incharge_api.get_stations)
        response.raise_for_status()
        stations = [station["name"] for station in response.json().get("stations")]
    except (
        ConnectionError,
        requests.exceptions.HTTPError,
    ) as incharge_connection_error:
        raise ConfigEntryAuthFailed from incharge_connection_error

    # Add entities for each charging station
    for station in stations:
        probe = InChargeData(incharge_api, station)

        entities = [
            InChargeSensor(
                probe,
                name=station,
                unique_id=f"{station}-{description.name}",
                description=description,
            )
            for _, description in SENSOR_TYPES.items()
        ]
        async_add_entities(entities, True)


class InChargeSensor(SensorEntity):
    """Representation of a InCharge Sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self, probe, name, unique_id, description: SensorEntityDescription
    ) -> None:
        """Initialize a PVOutput sensor."""
        self.probe = probe
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:ev-station"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, probe.station_id)},
            manufacturer="InCharge",
            name=name,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        result = self.probe.get_data(self.entity_description)
        if self.entity_description.suggested_display_precision is not None:
            result = round(result, self.entity_description.suggested_display_precision)
        return result

    def update(self) -> None:
        """Get the latest data from the InCharge API and updates the state."""
        self.probe.update()


class InChargeData:
    """The class for handling data retrieval."""

    def __init__(self, api: InCharge, station_id: str) -> None:
        """Initialize the probe."""
        self.api = api
        self.station_id = station_id
        self.data: dict[str, Any] = {}
        self.previous_values: dict[str, Any] = {}

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Update probe data."""
        _LOGGER.debug("Updating data for %s", self.station_id)
        try:
            response = self.api.get_station_consumption(self.station_id)
            response.raise_for_status()
            result = response.json()[0]["total"]
            self.data["total_energy_consumption"] = result
        except (
            ConnectionError,
            requests.exceptions.HTTPError,
        ) as incharge_connection_error:
            raise UpdateFailed from incharge_connection_error

    def get_data(self, entity_description: SensorEntityDescription) -> float | None:
        """Get data."""
        return self.data.get(entity_description.key)
