"""Support for Melnor RainCloud sprinkler water timer."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_RAINCLOUD, ICON_MAP
from .entity import RainCloudEntity

_LOGGER = logging.getLogger(__name__)

SENSORS = ["battery", "next_cycle", "rain_delay", "watering_time"]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(SENSORS)]
        )
    }
)

UNIT_OF_MEASUREMENT_MAP = {
    "auto_watering": "",
    "battery": PERCENTAGE,
    "is_watering": "",
    "manual_watering": "",
    "next_cycle": "",
    "rain_delay": UnitOfTime.DAYS,
    "status": "",
    "watering_time": UnitOfTime.MINUTES,
}


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
        if sensor_type == "battery":
            sensors.append(RainCloudSensor(raincloud.controller.faucet, sensor_type))
        else:
            # create a sensor for each zone managed by a faucet
            sensors.extend(
                RainCloudSensor(zone, sensor_type)
                for zone in raincloud.controller.faucet.zones
            )

    add_entities(sensors, True)


class RainCloudSensor(RainCloudEntity, SensorEntity):
    """A sensor implementation for raincloud device."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the units of measurement."""
        return UNIT_OF_MEASUREMENT_MAP.get(self._sensor_type)

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self._name)
        if self._sensor_type == "battery":
            self._state = self.data.battery
        else:
            self._state = getattr(self.data, self._sensor_type)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == "battery" and self._state is not None:
            return icon_for_battery_level(
                battery_level=int(self._state), charging=False
            )
        return ICON_MAP.get(self._sensor_type)
