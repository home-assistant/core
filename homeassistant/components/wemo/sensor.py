"""Support for power sensors in WeMo Insight devices."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity
from .wemo_device import DeviceCoordinator


@dataclass
class AttributeSensorDescription(SensorEntityDescription):
    """SensorEntityDescription for WeMo AttributeSensor entities."""

    # AttributeSensor does not support UNDEFINED,
    # restrict the type to str | None.
    name: str | None = None
    state_conversion: Callable[[StateType], StateType] | None = None
    unique_id_suffix: str | None = None


ATTRIBUTE_SENSORS = (
    AttributeSensorDescription(
        name="Current Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="current_power_watts",
        unique_id_suffix="currentpower",
        state_conversion=lambda state: round(cast(float, state), 2),
    ),
    AttributeSensorDescription(
        name="Today Energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="today_kwh",
        unique_id_suffix="todaymw",
        state_conversion=lambda state: round(cast(float, state), 2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo sensors."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        async_add_entities(
            AttributeSensor(coordinator, description)
            for description in ATTRIBUTE_SENSORS
            if hasattr(coordinator.wemo, description.key)
        )

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.sensor", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("sensor")
        )
    )


class AttributeSensor(WemoEntity, SensorEntity):
    """Sensor that reads attributes of a wemo device."""

    entity_description: AttributeSensorDescription

    def __init__(
        self, coordinator: DeviceCoordinator, description: AttributeSensorDescription
    ) -> None:
        """Init AttributeSensor."""
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def name_suffix(self) -> str | None:
        """Return the name of the entity."""
        return self.entity_description.name

    @property
    def unique_id_suffix(self) -> str | None:
        """Suffix to append to the WeMo device's unique ID."""
        return self.entity_description.unique_id_suffix

    def convert_state(self, value: StateType) -> StateType:
        """Convert native state to a value appropriate for the sensor."""
        if (convert := self.entity_description.state_conversion) is None:
            return None
        return convert(value)

    @property
    def native_value(self) -> StateType:
        """Return the value of the device attribute."""
        return self.convert_state(getattr(self.wemo, self.entity_description.key))
