"""Helper sensor for calculating utility costs."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
import logging
from typing import Any, Final, Literal, TypeVar, cast

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    DEVICE_CLASS_MONETARY,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.components.sensor.recorder import reset_detected
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .data import EnergyManager, async_get_manager

SUPPORTED_STATE_CLASSES = [
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the energy sensors."""
    sensor_manager = SensorManager(await async_get_manager(hass), async_add_entities)
    await sensor_manager.async_start()


T = TypeVar("T")


@dataclass
class SourceAdapter:
    """Adapter to allow sources and their flows to be used as sensors."""

    source_type: Literal["grid", "gas"]
    flow_type: Literal["flow_from", "flow_to", None]
    stat_energy_key: Literal["stat_energy_from", "stat_energy_to"]
    entity_energy_key: Literal["entity_energy_from", "entity_energy_to"]
    total_money_key: Literal["stat_cost", "stat_compensation"]
    name_suffix: str
    entity_id_suffix: str


SOURCE_ADAPTERS: Final = (
    SourceAdapter(
        "grid",
        "flow_from",
        "stat_energy_from",
        "entity_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
    SourceAdapter(
        "grid",
        "flow_to",
        "stat_energy_to",
        "entity_energy_to",
        "stat_compensation",
        "Compensation",
        "compensation",
    ),
    SourceAdapter(
        "gas",
        None,
        "stat_energy_from",
        "entity_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
)


class SensorManager:
    """Class to handle creation/removal of sensor data."""

    def __init__(
        self, manager: EnergyManager, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize sensor manager."""
        self.manager = manager
        self.async_add_entities = async_add_entities
        self.current_entities: dict[tuple[str, str | None, str], EnergyCostSensor] = {}

    async def async_start(self) -> None:
        """Start."""
        self.manager.async_listen_updates(self._process_manager_data)

        if self.manager.data:
            await self._process_manager_data()

    async def _process_manager_data(self) -> None:
        """Process manager data."""
        to_add: list[EnergyCostSensor] = []
        to_remove = dict(self.current_entities)

        async def finish() -> None:
            if to_add:
                self.async_add_entities(to_add)
                await asyncio.gather(*(ent.add_finished.wait() for ent in to_add))

            for key, entity in to_remove.items():
                self.current_entities.pop(key)
                await entity.async_remove()

        if not self.manager.data:
            await finish()
            return

        for energy_source in self.manager.data["energy_sources"]:
            for adapter in SOURCE_ADAPTERS:
                if adapter.source_type != energy_source["type"]:
                    continue

                if adapter.flow_type is None:
                    self._process_sensor_data(
                        adapter,
                        # Opting out of the type complexity because can't get it to work
                        energy_source,  # type: ignore
                        to_add,
                        to_remove,
                    )
                    continue

                for flow in energy_source[adapter.flow_type]:  # type: ignore
                    self._process_sensor_data(
                        adapter,
                        # Opting out of the type complexity because can't get it to work
                        flow,  # type: ignore
                        to_add,
                        to_remove,
                    )

        await finish()

    @callback
    def _process_sensor_data(
        self,
        adapter: SourceAdapter,
        config: dict,
        to_add: list[EnergyCostSensor],
        to_remove: dict[tuple[str, str | None, str], EnergyCostSensor],
    ) -> None:
        """Process sensor data."""
        # No need to create an entity if we already have a cost stat
        if config.get(adapter.total_money_key) is not None:
            return

        key = (adapter.source_type, adapter.flow_type, config[adapter.stat_energy_key])

        # Make sure the right data is there
        # If the entity existed, we don't pop it from to_remove so it's removed
        if config.get(adapter.entity_energy_key) is None or (
            config.get("entity_energy_price") is None
            and config.get("number_energy_price") is None
        ):
            return

        current_entity = to_remove.pop(key, None)
        if current_entity:
            current_entity.update_config(config)
            return

        self.current_entities[key] = EnergyCostSensor(
            adapter,
            config,
        )
        to_add.append(self.current_entities[key])


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.
    """

    _wrong_state_class_reported = False
    _wrong_unit_reported = False

    def __init__(
        self,
        adapter: SourceAdapter,
        config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._adapter = adapter
        self.entity_id = (
            f"{config[adapter.entity_energy_key]}_{adapter.entity_id_suffix}"
        )
        self._attr_device_class = DEVICE_CLASS_MONETARY
        self._attr_state_class = STATE_CLASS_TOTAL
        self._config = config
        self._last_energy_sensor_state: State | None = None
        # add_finished is set when either of async_added_to_hass or add_to_platform_abort
        # is called
        self.add_finished = asyncio.Event()

    def _reset(self, energy_state: State) -> None:
        """Reset the cost sensor."""
        self._attr_native_value = 0.0
        self._attr_last_reset = dt_util.utcnow()
        self._last_energy_sensor_state = energy_state
        self.async_write_ha_state()

    @callback
    def _update_cost(self) -> None:
        """Update incurred costs."""
        energy_state = self.hass.states.get(
            cast(str, self._config[self._adapter.entity_energy_key])
        )

        if energy_state is None:
            return

        state_class = energy_state.attributes.get(ATTR_STATE_CLASS)
        if state_class not in SUPPORTED_STATE_CLASSES:
            if not self._wrong_state_class_reported:
                self._wrong_state_class_reported = True
                _LOGGER.warning(
                    "Found unexpected state_class %s for %s",
                    state_class,
                    energy_state.entity_id,
                )
            return

        # last_reset must be set if the sensor is STATE_CLASS_MEASUREMENT
        if (
            state_class == STATE_CLASS_MEASUREMENT
            and ATTR_LAST_RESET not in energy_state.attributes
        ):
            return

        try:
            energy = float(energy_state.state)
        except ValueError:
            return

        # Determine energy price
        if self._config["entity_energy_price"] is not None:
            energy_price_state = self.hass.states.get(
                self._config["entity_energy_price"]
            )

            if energy_price_state is None:
                return

            try:
                energy_price = float(energy_price_state.state)
            except ValueError:
                return

            if (
                self._adapter.source_type == "grid"
                and energy_price_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT, ""
                ).endswith(f"/{ENERGY_WATT_HOUR}")
            ):
                energy_price *= 1000.0

        else:
            energy_price_state = None
            energy_price = cast(float, self._config["number_energy_price"])

        if self._last_energy_sensor_state is None:
            # Initialize as it's the first time all required entities are in place.
            self._reset(energy_state)
            return

        energy_unit = energy_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if self._adapter.source_type == "grid":
            if energy_unit == ENERGY_WATT_HOUR:
                energy_price /= 1000
            elif energy_unit != ENERGY_KILO_WATT_HOUR:
                energy_unit = None

        elif self._adapter.source_type == "gas":
            if energy_unit != VOLUME_CUBIC_METERS:
                energy_unit = None

        if energy_unit is None:
            if not self._wrong_unit_reported:
                self._wrong_unit_reported = True
                _LOGGER.warning(
                    "Found unexpected unit %s for %s",
                    energy_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                    energy_state.entity_id,
                )
            return

        if state_class != STATE_CLASS_TOTAL_INCREASING and energy_state.attributes.get(
            ATTR_LAST_RESET
        ) != self._last_energy_sensor_state.attributes.get(ATTR_LAST_RESET):
            # Energy meter was reset, reset cost sensor too
            energy_state_copy = copy.copy(energy_state)
            energy_state_copy.state = "0.0"
            self._reset(energy_state_copy)
        elif state_class == STATE_CLASS_TOTAL_INCREASING and reset_detected(
            self.hass,
            cast(str, self._config[self._adapter.entity_energy_key]),
            energy,
            float(self._last_energy_sensor_state.state),
        ):
            # Energy meter was reset, reset cost sensor too
            energy_state_copy = copy.copy(energy_state)
            energy_state_copy.state = "0.0"
            self._reset(energy_state_copy)
        # Update with newly incurred cost
        old_energy_value = float(self._last_energy_sensor_state.state)
        cur_value = cast(float, self._attr_native_value)
        self._attr_native_value = cur_value + (energy - old_energy_value) * energy_price

        self._last_energy_sensor_state = energy_state

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        energy_state = self.hass.states.get(
            self._config[self._adapter.entity_energy_key]
        )
        if energy_state:
            name = energy_state.name
        else:
            name = split_entity_id(self._config[self._adapter.entity_energy_key])[
                0
            ].replace("_", " ")

        self._attr_name = f"{name} {self._adapter.name_suffix}"

        self._update_cost()

        # Store stat ID in hass.data so frontend can look it up
        self.hass.data[DOMAIN]["cost_sensors"][
            self._config[self._adapter.entity_energy_key]
        ] = self.entity_id

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._update_cost()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                cast(str, self._config[self._adapter.entity_energy_key]),
                async_state_changed_listener,
            )
        )
        self.add_finished.set()

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        self.add_finished.set()

    async def async_will_remove_from_hass(self) -> None:
        """Handle removing from hass."""
        self.hass.data[DOMAIN]["cost_sensors"].pop(
            self._config[self._adapter.entity_energy_key]
        )
        await super().async_will_remove_from_hass()

    @callback
    def update_config(self, config: dict) -> None:
        """Update the config."""
        self._config = config

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self.hass.config.currency
