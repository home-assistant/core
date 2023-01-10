"""Support for monitoring the state of Vultr Subscriptions."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME, UnitOfInformation
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    ATTR_CURRENT_BANDWIDTH_USED,
    ATTR_PENDING_CHARGES,
    CONF_SUBSCRIPTION,
    DATA_VULTR,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Vultr {} {}"
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_CURRENT_BANDWIDTH_USED,
        name="Current Bandwidth Used",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:chart-histogram",
    ),
    SensorEntityDescription(
        key=ATTR_PENDING_CHARGES,
        name="Pending Charges",
        native_unit_of_measurement="US$",
        icon="mdi:currency-usd",
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SUBSCRIPTION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Vultr subscription (server) sensor."""
    vultr = hass.data[DATA_VULTR]

    subscription = config[CONF_SUBSCRIPTION]
    name = config[CONF_NAME]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    if subscription not in vultr.data:
        _LOGGER.error("Subscription %s not found", subscription)
        return

    entities = [
        VultrSensor(vultr, subscription, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


class VultrSensor(SensorEntity):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr, subscription, name, description: SensorEntityDescription):
        """Initialize a new Vultr sensor."""
        self.entity_description = description
        self._vultr = vultr
        self._name = name

        self.subscription = subscription
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return self._name.format(self.entity_description.name)
        except IndexError:
            try:
                return self._name.format(
                    self.data["label"], self.entity_description.name
                )
            except (KeyError, TypeError):
                return self._name

    @property
    def native_value(self):
        """Return the value of this given sensor type."""
        value = self.data.get(self.entity_description.key)
        if value == "not a number":
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return value

    def update(self) -> None:
        """Update state of sensor."""
        self._vultr.update()
        self.data = self._vultr.data[self.subscription]
