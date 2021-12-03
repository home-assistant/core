"""Support for OpenUV sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_OZONE, TIME_MINUTES, UV_INDEX
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
        name="Current Ozone Level",
        device_class=DEVICE_CLASS_OZONE,
        native_unit_of_measurement="du",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CURRENT_UV_INDEX,
        name="Current UV Index",
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CURRENT_UV_LEVEL,
        name="Current UV Level",
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key=TYPE_MAX_UV_INDEX,
        name="Max UV Index",
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_1,
        name="Skin Type 1 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_2,
        name="Skin Type 2 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_3,
        name="Skin Type 3 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_4,
        name="Skin Type 4 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_5,
        name="Skin Type 5 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_6,
        name="Skin Type 6 Safe Exposure Time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a OpenUV sensor based on a config entry."""
    openuv = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [OpenUvSensor(openuv, description) for description in SENSOR_DESCRIPTIONS]
    )


class OpenUvSensor(OpenUvEntity, SensorEntity):
    """Define a binary sensor for OpenUV."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if not (data := self.openuv.data[DATA_UV].get("result")):
            self._attr_available = False
            return

        self._attr_available = True

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
