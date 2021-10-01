"""Sensor support for Netgear Arlo IP cameras."""
from __future__ import annotations

from dataclasses import replace
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_MONITORED_CONDITIONS,
    DEVICE_CLASS_BATTERY,
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

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="last_capture",
        name="Last",
        icon="mdi:run-fast",
    ),
    SensorEntityDescription(
        key="total_cameras",
        name="Arlo Cameras",
        icon="mdi:video",
    ),
    SensorEntityDescription(
        key="captured_today",
        name="Captured Today",
        icon="mdi:file-video",
    ),
    SensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    SensorEntityDescription(
        key="signal_strength",
        name="Signal Strength",
        icon="mdi:signal",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key="air_quality",
        name="Air Quality",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:biohazard",
    ),
)

SENSOR_KEYS = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an Arlo IP sensor."""
    arlo = hass.data.get(DATA_ARLO)
    if not arlo:
        return

    sensors = []
    for sensor_original in SENSOR_TYPES:
        if sensor_original.key not in config[CONF_MONITORED_CONDITIONS]:
            continue
        sensor_entry = replace(sensor_original)
        if sensor_entry.key == "total_cameras":
            sensors.append(ArloSensor(arlo, sensor_entry))
        else:
            for camera in arlo.cameras:
                if sensor_entry.key in ("temperature", "humidity", "air_quality"):
                    continue

                sensor_entry.name = f"{sensor_entry.name} {camera.name}"
                sensors.append(ArloSensor(camera, sensor_entry))

            for base_station in arlo.base_stations:
                if (
                    sensor_entry.key in ("temperature", "humidity", "air_quality")
                    and base_station.model_id == "ABC1000"
                ):
                    sensor_entry.name = f"{sensor_entry.name} {base_station.name}"
                    sensors.append(ArloSensor(base_station, sensor_entry))

    add_entities(sensors, True)


class ArloSensor(SensorEntity):
    """An implementation of a Netgear Arlo IP sensor."""

    def __init__(self, device, sensor_entry):
        """Initialize an Arlo sensor."""
        self.entity_description = sensor_entry
        self._data = device
        self._state = None

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

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self.entity_description.key == "battery_level" and self._state is not None:
            return icon_for_battery_level(
                battery_level=int(self._state), charging=False
            )
        return self.entity_description.icon

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Arlo sensor %s", self.name)
        if self.entity_description.key == "total_cameras":
            self._state = len(self._data.cameras)

        elif self.entity_description.key == "captured_today":
            self._state = len(self._data.captured_today)

        elif self.entity_description.key == "last_capture":
            try:
                video = self._data.last_video
                self._state = video.created_at_pretty("%m-%d-%Y %H:%M:%S")
            except (AttributeError, IndexError):
                error_msg = (
                    f"Video not found for {self.name}. "
                    f"Older than {self._data.min_days_vdo_cache} days?"
                )
                _LOGGER.debug(error_msg)
                self._state = None

        elif self.entity_description.key == "battery_level":
            try:
                self._state = self._data.battery_level
            except TypeError:
                self._state = None

        elif self.entity_description.key == "signal_strength":
            try:
                self._state = self._data.signal_strength
            except TypeError:
                self._state = None

        elif self.entity_description.key == "temperature":
            try:
                self._state = self._data.ambient_temperature
            except TypeError:
                self._state = None

        elif self.entity_description.key == "humidity":
            try:
                self._state = self._data.ambient_humidity
            except TypeError:
                self._state = None

        elif self.entity_description.key == "air_quality":
            try:
                self._state = self._data.ambient_air_quality
            except TypeError:
                self._state = None

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        attrs["brand"] = DEFAULT_BRAND

        if self.entity_description.key != "total_cameras":
            attrs["model"] = self._data.model_id

        return attrs
