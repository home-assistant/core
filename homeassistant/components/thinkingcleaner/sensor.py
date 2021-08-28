"""Support for ThinkingCleaner sensors."""
from __future__ import annotations

from datetime import timedelta

from pythinkingcleaner import Discovery, ThinkingCleaner
import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_HOST, PERCENTAGE
import homeassistant.helpers.config_validation as cv

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="state",
        name="State",
    ),
    SensorEntityDescription(
        key="capacity",
        name="Capacity",
    ),
)

STATES = {
    "st_base": "On homebase: Not Charging",
    "st_base_recon": "On homebase: Reconditioning Charging",
    "st_base_full": "On homebase: Full Charging",
    "st_base_trickle": "On homebase: Trickle Charging",
    "st_base_wait": "On homebase: Waiting",
    "st_plug": "Plugged in: Not Charging",
    "st_plug_recon": "Plugged in: Reconditioning Charging",
    "st_plug_full": "Plugged in: Full Charging",
    "st_plug_trickle": "Plugged in: Trickle Charging",
    "st_plug_wait": "Plugged in: Waiting",
    "st_stopped": "Stopped",
    "st_clean": "Cleaning",
    "st_cleanstop": "Stopped with cleaning",
    "st_clean_spot": "Spot cleaning",
    "st_clean_max": "Max cleaning",
    "st_delayed": "Delayed cleaning will start soon",
    "st_dock": "Searching Homebase",
    "st_pickup": "Roomba picked up",
    "st_remote": "Remote control driving",
    "st_wait": "Waiting for command",
    "st_off": "Off",
    "st_error": "Error",
    "st_locate": "Find me!",
    "st_unknown": "Unknown state",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ThinkingCleaner platform."""

    host = config.get(CONF_HOST)
    if host:
        devices = [ThinkingCleaner(host, "unknown")]
    else:
        discovery = Discovery()
        devices = discovery.discover()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update all devices."""
        for device_object in devices:
            device_object.update()

    entities = [
        ThinkingCleanerSensor(device, update_devices, description)
        for device in devices
        for description in SENSOR_TYPES
    ]

    add_entities(entities)


class ThinkingCleanerSensor(SensorEntity):
    """Representation of a ThinkingCleaner Sensor."""

    def __init__(self, tc_object, update_devices, description: SensorEntityDescription):
        """Initialize the ThinkingCleaner."""
        self.entity_description = description
        self._tc_object = tc_object
        self._update_devices = update_devices

        self._attr_name = f"{tc_object.name} {description.name}"

    def update(self):
        """Update the sensor."""
        self._update_devices()

        sensor_type = self.entity_description.key
        if sensor_type == "battery":
            self._attr_native_value = self._tc_object.battery
        elif sensor_type == "state":
            self._attr_native_value = STATES[self._tc_object.status]
        elif sensor_type == "capacity":
            self._attr_native_value = self._tc_object.capacity
