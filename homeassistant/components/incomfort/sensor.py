"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DOMAIN, IncomfortChild

INCOMFORT_HEATER_TEMP = "CV Temp"
INCOMFORT_PRESSURE = "CV Pressure"
INCOMFORT_TAP_TEMP = "Tap Temp"


@dataclass(frozen=True)
class IncomfortSensorEntityDescription(SensorEntityDescription):
    """Describes Incomfort sensor entity."""

    extra_key: str | None = None
    # IncomfortSensor does not support UNDEFINED or None,
    # restrict the type to str
    name: str = ""


SENSOR_TYPES: tuple[IncomfortSensorEntityDescription, ...] = (
    IncomfortSensorEntityDescription(
        key="pressure",
        name=INCOMFORT_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    IncomfortSensorEntityDescription(
        key="heater_temp",
        name=INCOMFORT_HEATER_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_key="is_pumping",
    ),
    IncomfortSensorEntityDescription(
        key="tap_temp",
        name=INCOMFORT_TAP_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_key="is_tapping",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an InComfort/InTouch sensor device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    entities = [
        IncomfortSensor(client, heater, description)
        for heater in heaters
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class IncomfortSensor(IncomfortChild, SensorEntity):
    """Representation of an InComfort/InTouch sensor device."""

    entity_description: IncomfortSensorEntityDescription

    def __init__(
        self, client, heater, description: IncomfortSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.entity_description = description

        self._client = client
        self._heater = heater

        self._unique_id = f"{heater.serial_no}_{slugify(description.name)}"
        self.entity_id = f"{SENSOR_DOMAIN}.{DOMAIN}_{slugify(description.name)}"
        self._name = f"Boiler {description.name}"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._heater.status[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if (extra_key := self.entity_description.extra_key) is None:
            return None
        return {extra_key: self._heater.status[extra_key]}
