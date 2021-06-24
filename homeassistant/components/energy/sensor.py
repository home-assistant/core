"""Helper sensor for calculating utility costs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    DEVICE_CLASS_MONETARY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .data import async_get_manager


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the energy sensors."""
    manager = await async_get_manager(hass)

    if not manager.data:
        return

    entities = []

    currency = manager.data["currency"]
    for home_consumption in manager.data["home_consumption"]:
        if home_consumption["stat_cost"]:
            continue
        _, name = split_entity_id(home_consumption["entity_consumption"])
        energy_state = hass.states.get(home_consumption["entity_consumption"])
        if energy_state:
            name = energy_state.attributes.get(ATTR_NAME, name)
        name = f"{name} cost"
        entities.append(
            EnergyCostSensor(
                name,
                currency,
                home_consumption["entity_consumption"],
                home_consumption["entity_energy_price"],
                None,
            )
        )
    async_add_entities(entities)


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy."""

    def __init__(
        self,
        name: str,
        currency: str,
        energy_sensor: str,
        energy_price_sensor: str,
        hourly_price_sensor: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_name = name
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_unit_of_measurement = currency
        self._attr_unique_id = f"energy_{name}"

        self._energy_sensor_entity_id = energy_sensor
        self._energy_price_entity_id = energy_price_sensor
        self._hourly_price_entity_id = hourly_price_sensor

    def _update_cost(self) -> None:
        """Update incurred costs."""
        # TODO: This will use the same prices for the entire duration, we should
        # instead apply changed prices only after the price change.
        energy_state = self.hass.states.get(self._energy_sensor_entity_id)
        energy_price_state = self.hass.states.get(self._energy_price_entity_id)
        if self._hourly_price_entity_id:
            hourly_price_state = self.hass.states.get(self._hourly_price_entity_id)
        else:
            hourly_price_state = None
        if (
            energy_state is None
            or energy_price_state is None
            or (self._hourly_price_entity_id and hourly_price_state is None)
            or ATTR_LAST_RESET not in energy_state.attributes
        ):
            return
        last_reset = datetime.fromisoformat(energy_state.attributes[ATTR_LAST_RESET])
        now = dt_util.utcnow()

        energy = float(energy_state.state)
        energy_price = float(energy_price_state.state)
        duration_hours = (now - last_reset) / timedelta(hours=1)  # duration in hours
        if hourly_price_state:
            hourly_price = float(hourly_price_state.state)
        else:
            hourly_price = 0

        self._attr_last_reset = last_reset
        self._attr_state = energy * energy_price + duration_hours * hourly_price

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._update_cost()

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._update_cost()
            self.async_write_ha_state()

        entities = [self._energy_sensor_entity_id, self._energy_price_entity_id]
        if self._hourly_price_entity_id:
            entities.append(self._hourly_price_entity_id)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities, async_state_changed_listener
            )
        )
