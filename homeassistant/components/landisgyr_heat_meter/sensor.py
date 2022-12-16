"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import asdict
import logging

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .const import GJ_TO_MWH, HEAT_METER_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    unique_id = entry.entry_id
    coordinator = hass.data[DOMAIN][entry.entry_id]

    model = entry.data["model"]

    device = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Landis & Gyr",
        model=model,
        name="Landis+Gyr Heat Meter",
    )

    sensors = []

    for description in HEAT_METER_SENSOR_TYPES:
        sensors.append(HeatMeterSensor(coordinator, description, device))

    async_add_entities(sensors)


class HeatMeterSensor(CoordinatorEntity, RestoreSensor):
    """Representation of a Sensor."""

    def __init__(self, coordinator, description, device):
        """Set up the sensor with the initial values."""
        super().__init__(coordinator)
        self.key = description.key
        self._attr_unique_id = (
            f"{coordinator.config_entry.data['device_number']}_{description.key}"
        )
        self._attr_name = f"Heat Meter {description.name}"
        self.entity_description = description

        self._attr_device_info = device
        self._attr_should_poll = bool(self.key in ("heat_usage", "heat_previous_year"))

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.key in asdict(self.coordinator.data):
            if self.device_class == SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = dt_util.as_utc(
                    asdict(self.coordinator.data)[self.key]
                )
            else:
                self._attr_native_value = asdict(self.coordinator.data)[self.key]

        if self.key == "heat_usage":
            self._attr_native_value = convert_gj_to_mwh(
                self.coordinator.data.heat_usage_gj
            )

        if self.key == "heat_previous_year":
            self._attr_native_value = convert_gj_to_mwh(
                self.coordinator.data.heat_previous_year_gj
            )

        self.async_write_ha_state()


def convert_gj_to_mwh(gigajoule) -> float:
    """Convert GJ to MWh using the conversion value."""
    return round(gigajoule * GJ_TO_MWH, 5)
