"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import asdict
import logging

from ultraheat_api.response import HeatMeterResponse

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .const import HEAT_METER_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    unique_id = entry.entry_id
    coordinator: DataUpdateCoordinator[HeatMeterResponse] = hass.data[DOMAIN][
        entry.entry_id
    ]

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


class HeatMeterSensor(
    CoordinatorEntity[DataUpdateCoordinator[HeatMeterResponse]], RestoreSensor
):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HeatMeterResponse],
        description: SensorEntityDescription,
        device: DeviceInfo,
    ) -> None:
        """Set up the sensor with the initial values."""
        super().__init__(coordinator)
        self.key = description.key
        self._attr_unique_id = f"{coordinator.config_entry.data['device_number']}_{description.key}"  # type: ignore[union-attr]
        self._attr_name = f"Heat Meter {description.name}"
        self.entity_description = description

        self._attr_device_info = device

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            _LOGGER.debug(
                "Cannot update %s: could not read any data from the Heat Meter",
                self.key,
            )
            return

        if self.key in asdict(self.coordinator.data):
            if self.device_class == SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = dt_util.as_utc(
                    asdict(self.coordinator.data)[self.key]
                )
            else:
                self._attr_native_value = asdict(self.coordinator.data)[self.key]

        # Some models will supply MWh, these are handled here.
        if self.key == "heat_usage":
            if hasattr(self.coordinator.data, "heat_usage_mwh") and isinstance(
                self.coordinator.data.heat_usage_mwh, float
            ):
                self._attr_native_value = self.coordinator.data.heat_usage_mwh
            else:
                # Explicitly set it to None to prevent restored data to pop up
                self._attr_native_value = None

        if self.key == "heat_previous_year":
            if hasattr(self.coordinator.data, "heat_previous_year_mwh") and isinstance(
                self.coordinator.data.heat_previous_year_mwh, float
            ):
                self._attr_native_value = self.coordinator.data.heat_previous_year_mwh
            else:
                # Explicitly set it to None to prevent restored data to pop up
                self._attr_native_value = None

        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated value of %s",
            self.key,
        )
