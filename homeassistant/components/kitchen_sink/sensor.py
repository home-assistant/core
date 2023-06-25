"""Demo platform that has a couple of fake sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    async_add_entities(
        [
            DemoSensor(
                "statistics_issue_1",
                "Statistics issue 1",
                100,
                None,
                SensorStateClass.MEASUREMENT,
                UnitOfPower.WATT,  # Not a volume unit
            ),
            DemoSensor(
                "statistics_issue_2",
                "Statistics issue 2",
                100,
                None,
                SensorStateClass.MEASUREMENT,
                "dogs",  # Can't be converted to cats
            ),
            DemoSensor(
                "statistics_issue_3",
                "Statistics issue 3",
                100,
                None,
                None,  # Wrong state class
                UnitOfPower.WATT,
            ),
        ]
    )


class DemoSensor(SensorEntity):
    """Representation of a Demo sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: StateType,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_value = state
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )
