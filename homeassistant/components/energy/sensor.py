"""Helper sensor for calculating utility costs."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    DEVICE_CLASS_MONETARY,
    SensorEntity,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.util.dt as dt_util

# TODO: Spawn entities


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy."""

    def __init__(
        self,
        currency: str,
        energy_sensor: str,
        energy_price_sensor: str,
        hourly_price_sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_unit_of_measurement = currency

        self._energy_sensor_entity_id = energy_sensor
        self._energy_price_entity_id = energy_price_sensor
        self._hourly_price_entity_id = hourly_price_sensor

    def _update_cost(self) -> None:
        """Update incurred costs."""
        # TODO: This will use the same prices for the entire duration, we should
        # instead apply changed prices only after the price change.
        energy_state = self.hass.states.get(self._energy_sensor_entity_id)
        energy_price_state = self.hass.states.get(self._energy_sensor_entity_id)
        hourly_price_state = self.hass.states.get(self._energy_sensor_entity_id)
        if (
            energy_state is None
            or energy_price_state is None
            or hourly_price_state is None
            or ATTR_LAST_RESET not in energy_state.attributes
        ):
            return
        last_reset = energy_state.attributes[ATTR_LAST_RESET]
        now = dt_util.utcnow()

        energy = float(energy_state.state)
        energy_price = float(energy_price_state.state)
        duration_hours = now - last_reset / timedelta(hours=1)  # duration in hours
        hourly_price = float(hourly_price_state.state)

        self._attr_last_reset = last_reset
        self._attr_name = f"{energy_state.attributes[ATTR_NAME]} cost"
        self._attr_state = energy * energy_price + duration_hours * hourly_price

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._update_cost()

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._update_cost()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [
                    self._energy_sensor_entity_id,
                    self._energy_price_entity_id,
                    self._hourly_price_entity_id,
                ],
                async_state_changed_listener,
            )
        )
