"""Support for OpenUV sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_MINUTES, UV_INDEX
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, parse_datetime

from . import OpenUV, OpenUvEntity
from .const import (
    DATA_CLIENT,
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

SENSORS = {
    TYPE_CURRENT_OZONE_LEVEL: ("Current Ozone Level", "mdi:vector-triangle", "du"),
    TYPE_CURRENT_UV_INDEX: ("Current UV Index", "mdi:weather-sunny", UV_INDEX),
    TYPE_CURRENT_UV_LEVEL: ("Current UV Level", "mdi:weather-sunny", None),
    TYPE_MAX_UV_INDEX: ("Max UV Index", "mdi:weather-sunny", UV_INDEX),
    TYPE_SAFE_EXPOSURE_TIME_1: (
        "Skin Type 1 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
    TYPE_SAFE_EXPOSURE_TIME_2: (
        "Skin Type 2 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
    TYPE_SAFE_EXPOSURE_TIME_3: (
        "Skin Type 3 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
    TYPE_SAFE_EXPOSURE_TIME_4: (
        "Skin Type 4 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
    TYPE_SAFE_EXPOSURE_TIME_5: (
        "Skin Type 5 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
    TYPE_SAFE_EXPOSURE_TIME_6: (
        "Skin Type 6 Safe Exposure Time",
        "mdi:timer-outline",
        TIME_MINUTES,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a OpenUV sensor based on a config entry."""
    openuv = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensors = []
    for kind, attrs in SENSORS.items():
        name, icon, unit = attrs
        sensors.append(OpenUvSensor(openuv, kind, name, icon, unit))

    async_add_entities(sensors, True)


class OpenUvSensor(OpenUvEntity, SensorEntity):
    """Define a binary sensor for OpenUV."""

    def __init__(
        self, openuv: OpenUV, sensor_type: str, name: str, icon: str, unit: str | None
    ) -> None:
        """Initialize the sensor."""
        super().__init__(openuv, sensor_type)

        self._attr_icon = icon
        self._attr_name = name
        self._attr_unit_of_measurement = unit

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        data = self.openuv.data[DATA_UV].get("result")

        if not data:
            self._attr_available = False
            return

        self._attr_available = True

        if self._sensor_type == TYPE_CURRENT_OZONE_LEVEL:
            self._attr_state = data["ozone"]
        elif self._sensor_type == TYPE_CURRENT_UV_INDEX:
            self._attr_state = data["uv"]
        elif self._sensor_type == TYPE_CURRENT_UV_LEVEL:
            if data["uv"] >= 11:
                self._attr_state = UV_LEVEL_EXTREME
            elif data["uv"] >= 8:
                self._attr_state = UV_LEVEL_VHIGH
            elif data["uv"] >= 6:
                self._attr_state = UV_LEVEL_HIGH
            elif data["uv"] >= 3:
                self._attr_state = UV_LEVEL_MODERATE
            else:
                self._attr_state = UV_LEVEL_LOW
        elif self._sensor_type == TYPE_MAX_UV_INDEX:
            self._attr_state = data["uv_max"]
            uv_max_time = parse_datetime(data["uv_max_time"])
            if uv_max_time:
                self._attr_extra_state_attributes.update(
                    {ATTR_MAX_UV_TIME: as_local(uv_max_time)}
                )
        elif self._sensor_type in (
            TYPE_SAFE_EXPOSURE_TIME_1,
            TYPE_SAFE_EXPOSURE_TIME_2,
            TYPE_SAFE_EXPOSURE_TIME_3,
            TYPE_SAFE_EXPOSURE_TIME_4,
            TYPE_SAFE_EXPOSURE_TIME_5,
            TYPE_SAFE_EXPOSURE_TIME_6,
        ):
            self._attr_state = data["safe_exposure_time"][
                EXPOSURE_TYPE_MAP[self._sensor_type]
            ]
