"""Sensor support for Netgear Arlo IP cameras."""
import logging

import voluptuous as vol

from homeassistant.components.arlo.camera import ATTR_SIGNAL_STRENGTH
from homeassistant.components.climate.const import ATTR_HUMIDITY
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_LEVEL,
    ATTR_MODEL,
    ATTR_TEMPERATURE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_MONITORED_CONDITIONS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.icon import icon_for_battery_level

from . import ATTRIBUTION, DATA_ARLO, DEFAULT_BRAND, SIGNAL_UPDATE_ARLO

_LOGGER = logging.getLogger(__name__)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    "last_capture": ["Last", None, "run-fast"],
    "total_cameras": ["Arlo Cameras", None, "video"],
    "captured_today": ["Captured Today", None, "file-video"],
    ATTR_BATTERY_LEVEL: ["Battery Level", PERCENTAGE, "battery-50"],
    ATTR_SIGNAL_STRENGTH: ["Signal Strength", None, "signal"],
    ATTR_TEMPERATURE: ["Temperature", TEMP_CELSIUS, "thermometer"],
    ATTR_HUMIDITY: ["Humidity", PERCENTAGE, "water-percent"],
    "air_quality": ["Air Quality", CONCENTRATION_PARTS_PER_MILLION, "biohazard"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an Arlo IP sensor."""
    arlo = hass.data.get(DATA_ARLO)
    if not arlo:
        return

    sensors = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        if sensor_type == "total_cameras":
            sensors.append(ArloSensor(SENSOR_TYPES[sensor_type][0], arlo, sensor_type))
        else:
            for camera in arlo.cameras:
                if sensor_type in (ATTR_TEMPERATURE, ATTR_HUMIDITY, "air_quality"):
                    continue

                name = f"{SENSOR_TYPES[sensor_type][0]} {camera.name}"
                sensors.append(ArloSensor(name, camera, sensor_type))

            for base_station in arlo.base_stations:
                if (
                    sensor_type in (ATTR_TEMPERATURE, ATTR_HUMIDITY, "air_quality")
                    and base_station.model_id == "ABC1000"
                ):
                    name = f"{SENSOR_TYPES[sensor_type][0]} {base_station.name}"
                    sensors.append(ArloSensor(name, base_station, sensor_type))

    add_entities(sensors, True)


class ArloSensor(SensorEntity):
    """An implementation of a Netgear Arlo IP sensor."""

    def __init__(self, name, device, sensor_type):
        """Initialize an Arlo sensor."""
        _LOGGER.debug("ArloSensor created for %s", name)
        self._attr_name = name
        self._data = device
        self._sensor_type = sensor_type
        self._attr_unit_of_measurement = SENSOR_TYPES.get(sensor_type)[1]
        if sensor_type == ATTR_TEMPERATURE:
            self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        if sensor_type == ATTR_HUMIDITY:
            self._attr_device_class = DEVICE_CLASS_HUMIDITY

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ARLO, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Arlo sensor %s", self.name)
        if self._sensor_type == "total_cameras":
            self._attr_state = len(self._data.cameras)

        elif self._sensor_type == "captured_today":
            self._attr_state = len(self._data.captured_today)

        elif self._sensor_type == "last_capture":
            try:
                video = self._data.last_video
                self._attr_state = video.created_at_pretty("%m-%d-%Y %H:%M:%S")
            except (AttributeError, IndexError):
                error_msg = (
                    f"Video not found for {self.name}. "
                    f"Older than {self._data.min_days_vdo_cache} days?"
                )
                _LOGGER.debug(error_msg)
                self._attr_state = None

        elif self._sensor_type == ATTR_BATTERY_LEVEL:
            try:
                self._attr_state = self._data.battery_level
            except TypeError:
                self._attr_state = None

        elif self._sensor_type == ATTR_SIGNAL_STRENGTH:
            try:
                self._attr_state = self._data.signal_strength
            except TypeError:
                self._attr_state = None

        elif self._sensor_type == ATTR_TEMPERATURE:
            try:
                self._attr_state = self._data.ambient_temperature
            except TypeError:
                self._attr_state = None

        elif self._sensor_type == ATTR_HUMIDITY:
            try:
                self._attr_state = self._data.ambient_humidity
            except TypeError:
                self._attr_state = None

        elif self._sensor_type == "air_quality":
            try:
                self._attr_state = self._data.ambient_air_quality
            except TypeError:
                self._attr_state = None
        if self._sensor_type == ATTR_BATTERY_LEVEL and self._attr_state is not None:
            self._attr_icon = icon_for_battery_level(
                battery_level=int(self._attr_state), charging=False
            )
        else:
            self._attr_icon = f"mdi:{SENSOR_TYPES.get(self._sensor_type)[2]}"
        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        self._attr_extra_state_attributes["brand"] = DEFAULT_BRAND
        if self._sensor_type != "total_cameras":
            self._attr_extra_state_attributes[ATTR_MODEL] = self._data.model_id
