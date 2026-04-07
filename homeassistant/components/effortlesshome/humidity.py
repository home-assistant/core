"""Humidity sensor."""

from functools import cached_property
from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import PERCENTAGE

from .auto_area import AutoArea
from .auto_entity import AutoEntity
from .const import HUMIDITY_SENSOR_ENTITY_PREFIX, HUMIDITY_SENSOR_PREFIX


class HumiditySensor(AutoEntity[SensorEntity, SensorDeviceClass], SensorEntity):
    """Set up aggregated humidity sensor."""

    def __init__(self, hass, auto_area: AutoArea) -> None:
        """Initialize sensor."""
        super().__init__(
            hass,
            auto_area,
            SensorDeviceClass.HUMIDITY,
            HUMIDITY_SENSOR_PREFIX,
            HUMIDITY_SENSOR_ENTITY_PREFIX,
        )

    @override
    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        return PERCENTAGE

    @override
    @property
    def state(self) -> Any:  # type: ignore
        """Return the state of the entity."""
        return self._aggregated_state

    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self.state = last_state.state