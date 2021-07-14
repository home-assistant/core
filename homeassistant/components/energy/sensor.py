"""Helper sensor for calculating utility costs."""
from __future__ import annotations

from functools import partial
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

from .data import EnergyManager, FlowFromGridSourceType, async_get_manager


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the energy sensors."""
    manager = await async_get_manager(hass)
    process_now = partial(_process_manager_data, hass, manager, async_add_entities, {})
    manager.async_listen_updates(process_now)

    if manager.data:
        await process_now()


async def _process_manager_data(
    hass: HomeAssistant,
    manager: EnergyManager,
    async_add_entities: AddEntitiesCallback,
    current_entities: dict[str, EnergyCostSensor],
) -> None:
    """Process updated data."""
    to_add = []
    to_remove = dict(current_entities)

    if manager.data:
        for energy_source in manager.data["energy_sources"]:
            if energy_source["type"] != "grid":
                continue

            for flow in energy_source["flow_from"]:
                # No need to create an entity if we already have a cost stat
                if flow["stat_cost"] is not None:
                    continue

                # This is unique among all flow_from's
                key = flow["stat_energy_from"]

                current_entity = to_remove.pop(key, None)
                if current_entity:
                    current_entity.update_config(flow)
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

                current_entities[key] = EnergyCostSensor(
                    f"{name} cost",
                    manager.data["currency"],
                    flow,
                )
                to_add.append(current_entities[key])

    if to_add:
        async_add_entities(to_add)

    for key, entity in to_remove.items():
        current_entities.pop(key)
        await entity.async_remove()


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.
    """

    def __init__(
        self,
        name: str,
        currency: str,
        flow: FlowFromGridSourceType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_name = name
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_unit_of_measurement = currency
        self._flow = flow
        self._last_energy_sensor_state: State | None = None

    def _reset(self, energy_state: State) -> None:
        """Reset the cost sensor."""
        self._attr_state = 0.0
        self._attr_last_reset = dt_util.utcnow()
        self._last_energy_sensor_state = energy_state
        self.async_write_ha_state()

    @callback
    def _update_cost(self) -> None:
        """Update incurred costs."""
        energy_state = self.hass.states.get(cast(str, self._flow["entity_energy_from"]))

        if energy_state is None or ATTR_LAST_RESET not in energy_state.attributes:
            return

        try:
            energy = float(energy_state.state)
        except ValueError:
            return

        # Determine energy price
        if self._flow["entity_energy_price"] is not None:
            energy_price_state = self.hass.states.get(self._flow["entity_energy_price"])

            if energy_price_state is None:
                return

            try:
                energy_price = float(energy_price_state.state)
            except ValueError:
                return
        else:
            energy_price_state = None
            energy_price = cast(float, self._flow["number_energy_price"])

        if self._last_energy_sensor_state is None:
            # Initialize as it's the first time all required entities are in place.
            self._reset(energy_state)
            return

        cur_value = cast(float, self._attr_state)
        if (
            energy_state.attributes[ATTR_LAST_RESET]
            != self._last_energy_sensor_state.attributes[ATTR_LAST_RESET]
        ):
            # Energy meter was reset, reset cost sensor too
            self._reset(energy_state)
        else:
            # Update with newly incurred cost
            old_energy_value = float(self._last_energy_sensor_state.state)
            self._attr_state = cur_value + (energy - old_energy_value) * energy_price

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
                self.hass,
                cast(str, self._flow["entity_energy_from"]),
                async_state_changed_listener,
            )
        )

    @callback
    def update_config(self, flow: FlowFromGridSourceType) -> None:
        """Update the config."""
        self._flow = flow
