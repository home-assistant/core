"""Support for sensors from the Dovado router."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import re

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_SENSORS, PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SENSOR_UPLOAD = "upload"
SENSOR_DOWNLOAD = "download"
SENSOR_SIGNAL = "signal"
SENSOR_NETWORK = "network"
SENSOR_SMS_UNREAD = "sms"


@dataclass(frozen=True, kw_only=True)
class DovadoSensorEntityDescription(SensorEntityDescription):
    """Describes Dovado sensor entity."""

    identifier: str


SENSOR_TYPES: tuple[DovadoSensorEntityDescription, ...] = (
    DovadoSensorEntityDescription(
        identifier=SENSOR_NETWORK,
        key="signal strength",
        name="Network",
        icon="mdi:access-point-network",
    ),
    DovadoSensorEntityDescription(
        identifier=SENSOR_SIGNAL,
        key="signal strength",
        name="Signal Strength",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:signal",
    ),
    DovadoSensorEntityDescription(
        identifier=SENSOR_SMS_UNREAD,
        key="sms unread",
        name="SMS unread",
        icon="mdi:message-text-outline",
    ),
    DovadoSensorEntityDescription(
        identifier=SENSOR_UPLOAD,
        key="traffic modem tx",
        name="Sent",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:cloud-upload",
    ),
    DovadoSensorEntityDescription(
        identifier=SENSOR_DOWNLOAD,
        key="traffic modem rx",
        name="Received",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:cloud-download",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSOR_KEYS)])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dovado sensor platform."""
    dovado = hass.data[DOMAIN]

    sensors = config[CONF_SENSORS]
    entities = [
        DovadoSensor(dovado, description)
        for description in SENSOR_TYPES
        if description.key in sensors
    ]
    add_entities(entities)


class DovadoSensor(SensorEntity):
    """Representation of a Dovado sensor."""

    entity_description: DovadoSensorEntityDescription

    def __init__(self, data, description: DovadoSensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._data = data

        self._attr_name = f"{data.name} {description.name}"
        self._attr_native_value = self._compute_state()

    def _compute_state(self):
        """Compute the state of the sensor."""
        state = self._data.state.get(self.entity_description.key)
        sensor_identifier = self.entity_description.identifier
        if sensor_identifier == SENSOR_NETWORK:
            match = re.search(r"\((.+)\)", state)
            return match.group(1) if match else None
        if sensor_identifier == SENSOR_SIGNAL:
            try:
                return int(state.split()[0])
            except ValueError:
                return None
        if sensor_identifier == SENSOR_SMS_UNREAD:
            return int(state)
        if sensor_identifier in [SENSOR_UPLOAD, SENSOR_DOWNLOAD]:
            return round(float(state) / 1e6, 1)
        return state

    def update(self) -> None:
        """Update sensor values."""
        self._data.update()
        self._attr_native_value = self._compute_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {k: v for k, v in self._data.state.items() if k not in ["date", "time"]}
