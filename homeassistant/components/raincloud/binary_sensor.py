"""Support for Melnor RainCloud sprinkler water timer."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_RAINCLOUD
from .entity import RainCloudEntity

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = ["is_watering", "status"]

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSORS)]
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a raincloud device."""
    raincloud = hass.data[DATA_RAINCLOUD].data

    sensors = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        if sensor_type == "status":
            sensors.append(RainCloudBinarySensor(raincloud.controller, sensor_type))
            sensors.append(
                RainCloudBinarySensor(raincloud.controller.faucet, sensor_type)
            )

        else:
            # create a sensor for each zone managed by faucet
            sensors.extend(
                RainCloudBinarySensor(zone, sensor_type)
                for zone in raincloud.controller.faucet.zones
            )

    add_entities(sensors, True)


class RainCloudBinarySensor(RainCloudEntity, BinarySensorEntity):
    """A sensor implementation for raincloud device."""

    def update(self) -> None:
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self.name)
        state = getattr(self.data, self._sensor_type)
        if self._sensor_type == "status":
            self._attr_is_on = state == "Online"
        else:
            self._attr_is_on = state

    @property
    def icon(self) -> str | None:
        """Return the icon of this device."""
        if self._sensor_type == "is_watering":
            return "mdi:water" if self.is_on else "mdi:water-off"
        if self._sensor_type == "status":
            return "mdi:pipe" if self.is_on else "mdi:pipe-disconnected"
        return super().icon
