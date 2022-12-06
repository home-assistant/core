"""Support for OpenUV sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_MINUTES, UV_INDEX
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, parse_datetime

from . import OpenUvEntity
from .const import (
    DATA_UV,
    DOMAIN,
    TYPE_CURRENT_OZONE_LEVEL,
    TYPE_CURRENT_UV_INDEX,
    TYPE_CURRENT_UV_LEVEL,
    TYPE_MAX_UV_INDEX,
    TYPE_SAFE_EXPOSURE_TIME_1,
    TYPE_SAFE_EXPOSURE_TIME_2,
    TYPE_SAFE_EXPOSURE_TIME_3,
    TYPE_SAFE_EXPOSURE_TIME_4,
    TYPE_SAFE_EXPOSURE_TIME_5,
    TYPE_SAFE_EXPOSURE_TIME_6,
)
from .coordinator import OpenUvCoordinator

ATTR_MAX_UV_TIME = "time"

EXPOSURE_TYPE_MAP = {
    TYPE_SAFE_EXPOSURE_TIME_1: "st1",
    TYPE_SAFE_EXPOSURE_TIME_2: "st2",
    TYPE_SAFE_EXPOSURE_TIME_3: "st3",
    TYPE_SAFE_EXPOSURE_TIME_4: "st4",
    TYPE_SAFE_EXPOSURE_TIME_5: "st5",
    TYPE_SAFE_EXPOSURE_TIME_6: "st6",
}

UV_LEVEL_EXTREME = "Extreme"
UV_LEVEL_VHIGH = "Very High"
UV_LEVEL_HIGH = "High"
UV_LEVEL_MODERATE = "Moderate"
UV_LEVEL_LOW = "Low"

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_CURRENT_OZONE_LEVEL,
        name="Current ozone level",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement="du",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CURRENT_UV_INDEX,
        name="Current UV index",
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CURRENT_UV_LEVEL,
        name="Current UV level",
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key=TYPE_MAX_UV_INDEX,
        name="Max UV index",
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_1,
        name="Skin type 1 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_2,
        name="Skin type 2 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_3,
        name="Skin type 3 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_4,
        name="Skin type 4 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_5,
        name="Skin type 5 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_6,
        name="Skin type 6 safe exposure time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a OpenUV sensor based on a config entry."""
    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            OpenUvSensor(coordinators[DATA_UV], description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class OpenUvSensor(OpenUvEntity, SensorEntity):
    """Define a binary sensor for OpenUV."""

    @callback
    def _update_from_latest_data(self) -> None:
        """Update the state."""
        data = self.coordinator.data

        if self.entity_description.key == TYPE_CURRENT_OZONE_LEVEL:
            self._attr_native_value = data["ozone"]
        elif self.entity_description.key == TYPE_CURRENT_UV_INDEX:
            self._attr_native_value = data["uv"]
        elif self.entity_description.key == TYPE_CURRENT_UV_LEVEL:
            if data["uv"] >= 11:
                self._attr_native_value = UV_LEVEL_EXTREME
            elif data["uv"] >= 8:
                self._attr_native_value = UV_LEVEL_VHIGH
            elif data["uv"] >= 6:
                self._attr_native_value = UV_LEVEL_HIGH
            elif data["uv"] >= 3:
                self._attr_native_value = UV_LEVEL_MODERATE
            else:
                self._attr_native_value = UV_LEVEL_LOW
        elif self.entity_description.key == TYPE_MAX_UV_INDEX:
            self._attr_native_value = data["uv_max"]
            if uv_max_time := parse_datetime(data["uv_max_time"]):
                self._attr_extra_state_attributes.update(
                    {ATTR_MAX_UV_TIME: as_local(uv_max_time)}
                )
        elif self.entity_description.key in (
            TYPE_SAFE_EXPOSURE_TIME_1,
            TYPE_SAFE_EXPOSURE_TIME_2,
            TYPE_SAFE_EXPOSURE_TIME_3,
            TYPE_SAFE_EXPOSURE_TIME_4,
            TYPE_SAFE_EXPOSURE_TIME_5,
            TYPE_SAFE_EXPOSURE_TIME_6,
        ):
            self._attr_native_value = data["safe_exposure_time"][
                EXPOSURE_TYPE_MAP[self.entity_description.key]
            ]
