"""Sensor support for Skybell Doorbells."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DEFAULT_ENTITY_NAMESPACE, DOMAIN as SKYBELL_DOMAIN, SkybellDevice

SCAN_INTERVAL = timedelta(seconds=30)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chime_level",
        name="Chime Level",
        icon="mdi:bell-ring",
    ),
)
MONITORED_CONDITIONS: list[str] = [desc.key for desc in SENSOR_TYPES]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE
        ): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a Skybell device."""
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = [
        SkybellSensor(device, description)
        for device in skybell.get_devices()
        for description in SENSOR_TYPES
        if description.key in config[CONF_MONITORED_CONDITIONS]
    ]

    add_entities(sensors, True)


class SkybellSensor(SkybellDevice, SensorEntity):
    """A sensor implementation for Skybell devices."""

    def __init__(
        self,
        device,
        description: SensorEntityDescription,
    ):
        """Initialize a sensor for a Skybell device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{self._device.name} {description.name}"

    def update(self):
        """Get the latest data and updates the state."""
        super().update()

        if self.entity_description.key == "chime_level":
            self._attr_native_value = self._device.outdoor_chime_level
