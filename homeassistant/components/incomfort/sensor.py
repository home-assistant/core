"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from incomfortclient import Gateway as InComfortGateway, Heater as InComfortHeater

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import DATA_INCOMFORT, IncomfortEntity
from .const import DOMAIN

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InComfort/InTouch sensor entities."""
    incomfort_data = hass.data[DATA_INCOMFORT][entry.entry_id]
    async_add_entities(
        IncomfortSensor(incomfort_data.client, heater, description)
        for heater in incomfort_data.heaters
        for description in SENSOR_TYPES
    )


class IncomfortSensor(IncomfortEntity, SensorEntity):
    """Representation of an InComfort/InTouch sensor device."""

    entity_description: IncomfortSensorEntityDescription

    def __init__(
        self,
        client: InComfortGateway,
        heater: InComfortHeater,
        description: IncomfortSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.entity_description = description

        self._client = client
        self._heater = heater

        self._attr_unique_id = f"{heater.serial_no}_{slugify(description.name)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heater.serial_no)},
            manufacturer="Intergas",
            name="Boiler",
        )

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
