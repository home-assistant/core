"""Support for Hydrawise sprinkler binary sensors."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_HYDRAWISE, HydrawiseEntity

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_STATUS = BinarySensorEntityDescription(
    key="status",
    name="Status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_watering",
        name="Watering",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)

BINARY_SENSOR_KEYS: list[str] = [
    desc.key for desc in (BINARY_SENSOR_STATUS, *BINARY_SENSOR_TYPES)
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=BINARY_SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSOR_KEYS)]
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    entities = []
    if BINARY_SENSOR_STATUS.key in monitored_conditions:
        entities.append(
            HydrawiseBinarySensor(hydrawise.current_controller, BINARY_SENSOR_STATUS)
        )

    # create a sensor for each zone
    entities.extend(
        [
            HydrawiseBinarySensor(zone, description)
            for zone in hydrawise.relays
            for description in BINARY_SENSOR_TYPES
            if description.key in monitored_conditions
        ]
    )

    add_entities(entities, True)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    def update(self) -> None:
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Hydrawise binary sensor: %s", self.name)
        mydata = self.hass.data[DATA_HYDRAWISE].data
        if self.entity_description.key == "status":
            self._attr_is_on = mydata.status == "All good!"
        elif self.entity_description.key == "is_watering":
            relay_data = mydata.relays[self.data["relay"] - 1]
            self._attr_is_on = relay_data["timestr"] == "Now"
