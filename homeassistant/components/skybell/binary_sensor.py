"""Binary sensor support for the Skybell HD Doorbell."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DEFAULT_ENTITY_NAMESPACE, DOMAIN as SKYBELL_DOMAIN, SkybellDevice

SCAN_INTERVAL = timedelta(seconds=10)


BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "button": BinarySensorEntityDescription(
        key="device:sensor:button",
        name="Button",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    "motion": BinarySensorEntityDescription(
        key="device:sensor:motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE
        ): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform for a Skybell device."""
    skybell = hass.data[SKYBELL_DOMAIN]

    binary_sensors = [
        SkybellBinarySensor(device, BINARY_SENSOR_TYPES[sensor_type])
        for device in skybell.get_devices()
        for sensor_type in config[CONF_MONITORED_CONDITIONS]
    ]

    add_entities(binary_sensors, True)


class SkybellBinarySensor(SkybellDevice, BinarySensorEntity):
    """A binary sensor implementation for Skybell devices."""

    def __init__(
        self,
        device,
        description: BinarySensorEntityDescription,
    ):
        """Initialize a binary sensor for a Skybell device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{self._device.name} {description.name}"
        self._event: dict[Any, Any] = {}

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        attrs["event_date"] = self._event.get("createdAt")

        return attrs

    def update(self):
        """Get the latest data and updates the state."""
        super().update()

        event = self._device.latest(self.entity_description.key)

        self._attr_is_on = bool(event and event.get("id") != self._event.get("id"))

        self._event = event or {}
