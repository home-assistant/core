"""Helper sensor for calculating utility costs."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, Final, Literal, TypeVar, cast

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    DEVICE_CLASS_MONETARY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .data import EnergyManager, async_get_manager

_LOGGER = logging.getLogger(__name__)


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


T = TypeVar("T")


@dataclass
class FlowAdapter:
    """Adapter to allow flows to be used as sensors."""

    flow_type: Literal["flow_from", "flow_to"]
    stat_energy_key: Literal["stat_energy_from", "stat_energy_to"]
    entity_energy_key: Literal["entity_energy_from", "entity_energy_to"]
    total_money_key: Literal["stat_cost", "stat_compensation"]
    name_suffix: str
    entity_id_suffix: str


FLOW_ADAPTERS: Final = (
    FlowAdapter(
        "flow_from",
        "stat_energy_from",
        "entity_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
    FlowAdapter(
        "flow_to",
        "stat_energy_to",
        "entity_energy_to",
        "stat_compensation",
        "Compensation",
        "compensation",
    ),
)


async def _process_manager_data(
    hass: HomeAssistant,
    manager: EnergyManager,
    async_add_entities: AddEntitiesCallback,
    current_entities: dict[tuple[str, str], EnergyCostSensor],
) -> None:
    """Process updated data."""
    to_add: list[SensorEntity] = []
    to_remove = dict(current_entities)

    async def finish() -> None:
        if to_add:
            async_add_entities(to_add)

        for key, entity in to_remove.items():
            current_entities.pop(key)
            await entity.async_remove()

    if not manager.data:
        await finish()
        return

    for energy_source in manager.data["energy_sources"]:
        if energy_source["type"] != "grid":
            continue

        for adapter in FLOW_ADAPTERS:
            for flow in energy_source[adapter.flow_type]:
                # Opting out of the type complexity because can't get it to work
                untyped_flow = cast(dict, flow)

                # No need to create an entity if we already have a cost stat
                if untyped_flow.get(adapter.total_money_key) is not None:
                    continue

                # This is unique among all flow_from's
                key = (adapter.flow_type, untyped_flow[adapter.stat_energy_key])

                # Make sure the right data is there
                # If the entity existed, we don't pop it from to_remove so it's removed
                if untyped_flow.get(adapter.entity_energy_key) is None or (
                    untyped_flow.get("entity_energy_price") is None
                    and untyped_flow.get("number_energy_price") is None
                ):
                    continue

                current_entity = to_remove.pop(key, None)
                if current_entity:
                    current_entity.update_config(untyped_flow)
                    continue

                current_entities[key] = EnergyCostSensor(
                    adapter,
                    untyped_flow,
                )
                to_add.append(current_entities[key])

    await finish()


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.
    """

    def __init__(
        self,
        adapter: FlowAdapter,
        flow: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._adapter = adapter
        self.entity_id = f"{flow[adapter.entity_energy_key]}_{adapter.entity_id_suffix}"
        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._flow = flow
        self._last_energy_sensor_state: State | None = None
        self._cur_value = 0.0

    def _reset(self, energy_state: State) -> None:
        """Reset the cost sensor."""
        self._attr_state = 0.0
        self._cur_value = 0.0
        self._attr_last_reset = dt_util.utcnow()
        self._last_energy_sensor_state = energy_state
        self.async_write_ha_state()

    @callback
    def _update_cost(self) -> None:
        """Update incurred costs."""
        energy_state = self.hass.states.get(
            cast(str, self._flow[self._adapter.entity_energy_key])
        )

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

            if energy_price_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, "").endswith(
                f"/{ENERGY_WATT_HOUR}"
            ):
                energy_price *= 1000.0

        else:
            energy_price_state = None
            energy_price = cast(float, self._flow["number_energy_price"])

        if self._last_energy_sensor_state is None:
            # Initialize as it's the first time all required entities are in place.
            self._reset(energy_state)
            return

        energy_unit = energy_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if energy_unit == ENERGY_WATT_HOUR:
            energy_price /= 1000
        elif energy_unit != ENERGY_KILO_WATT_HOUR:
            _LOGGER.warning(
                "Found unexpected unit %s for %s", energy_unit, energy_state.entity_id
            )
            return

        if (
            energy_state.attributes[ATTR_LAST_RESET]
            != self._last_energy_sensor_state.attributes[ATTR_LAST_RESET]
        ):
            # Energy meter was reset, reset cost sensor too
            self._reset(energy_state)
        else:
            # Update with newly incurred cost
            old_energy_value = float(self._last_energy_sensor_state.state)
            self._cur_value += (energy - old_energy_value) * energy_price
            self._attr_state = round(self._cur_value, 2)

        self._last_energy_sensor_state = energy_state

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        energy_state = self.hass.states.get(self._flow[self._adapter.entity_energy_key])
        if energy_state:
            name = energy_state.name
        else:
            name = split_entity_id(self._flow[self._adapter.entity_energy_key])[
                0
            ].replace("_", " ")

        self._attr_name = f"{name} {self._adapter.name_suffix}"

        self._update_cost()

        # Store stat ID in hass.data so frontend can look it up
        self.hass.data[DOMAIN]["cost_sensors"][
            self._flow[self._adapter.entity_energy_key]
        ] = self.entity_id

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._update_cost()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                cast(str, self._flow[self._adapter.entity_energy_key]),
                async_state_changed_listener,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle removing from hass."""
        self.hass.data[DOMAIN]["cost_sensors"].pop(
            self._flow[self._adapter.entity_energy_key]
        )
        await super().async_will_remove_from_hass()

    @callback
    def update_config(self, flow: dict) -> None:
        """Update the config."""
        self._flow = flow

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self.hass.config.currency
