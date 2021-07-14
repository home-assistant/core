"""Helper sensor for calculating utility costs."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    DEVICE_CLASS_MONETARY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
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

    for energy_source in manager.data["energy_sources"]:
        if energy_source["type"] != "grid":
            continue

        for flow in energy_source["flow_from"]:
            # No need to create an entity if we already
            if flow["stat_cost"] is not None:
                continue

            # Make sure the right data is there
            if flow["entity_energy_from"] is None or (
                flow["entity_energy_price"] is None
                and flow["number_energy_price"] is None
            ):
                continue

            _, name = split_entity_id(flow["entity_energy_from"])
            energy_state = hass.states.get(flow["entity_energy_from"])
            if energy_state:
                name = energy_state.attributes.get(ATTR_NAME, name)

            entities.append(
                EnergyCostSensor(
                    f"{name} cost",
                    currency,
                    flow["entity_energy_from"],
                    flow["entity_energy_price"],
                    flow["number_energy_price"],
                )
            )

    async_add_entities(entities)


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.
    """

    def __init__(
        self,
        name: str,
        currency: str,
        energy_sensor: str,
        energy_price_sensor: str | None,
        number_energy_price: float | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_name = name
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_unit_of_measurement = currency

        self._energy_sensor_entity_id = energy_sensor
        self._energy_price_entity_id = energy_price_sensor
        self._number_energy_price = number_energy_price

        self._last_energy_sensor_state: State | None = None

    @callback
    def _update_cost(self) -> None:
        """Update incurred costs."""
        energy_state = self.hass.states.get(self._energy_sensor_entity_id)

        if energy_state is None or ATTR_LAST_RESET not in energy_state.attributes:
            return

        try:
            energy = float(energy_state.state)
        except ValueError:
            return

        # Determine energy price
        if self._energy_price_entity_id is not None:
            energy_price_state = self.hass.states.get(self._energy_price_entity_id)

            if energy_price_state is None:
                return

            try:
                energy_price = float(energy_price_state.state)
            except ValueError:
                return
        else:
            energy_price_state = None
            energy_price = cast(float, self._number_energy_price)

        if self._last_energy_sensor_state is None:
            # Initialize as it's the first time all required entities are in place.
            self._attr_state = 0.0
            self._attr_last_reset = dt_util.utcnow()
            self._last_energy_sensor_state = energy_state
            self.async_write_ha_state()
            return

        # If meter got reset, just take the new value.
        if (
            energy_state.attributes[ATTR_LAST_RESET]
            != self._last_energy_sensor_state.attributes[ATTR_LAST_RESET]
        ):
            self._attr_state = energy * energy_price
        else:
            old_energy_value = float(self._last_energy_sensor_state.state)
            self._attr_state = (
                cast(float, self._attr_state)
                + (energy - old_energy_value) * energy_price
            )

        self._last_energy_sensor_state = energy_state

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
                self.hass, self._energy_sensor_entity_id, async_state_changed_listener
            )
        )
