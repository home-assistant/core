"""Helper sensor for calculating utility costs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass
import logging
from typing import Any, Final, Literal, cast

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import (  # pylint: disable=hass-component-root-import
    reset_detected,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import (
    HomeAssistant,
    State,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, unit_conversion
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN
from .data import EnergyManager, PowerConfig, async_get_manager
from .helpers import generate_power_sensor_entity_id, generate_power_sensor_unique_id

SUPPORTED_STATE_CLASSES = {
    SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING,
}
VALID_ENERGY_UNITS: set[str] = set(UnitOfEnergy)

VALID_ENERGY_UNITS_GAS = {
    UnitOfVolume.CENTUM_CUBIC_FEET,
    UnitOfVolume.CUBIC_FEET,
    UnitOfVolume.CUBIC_METERS,
    UnitOfVolume.LITERS,
    UnitOfVolume.MILLE_CUBIC_FEET,
    *VALID_ENERGY_UNITS,
}
VALID_VOLUME_UNITS_WATER: set[str] = {
    UnitOfVolume.CENTUM_CUBIC_FEET,
    UnitOfVolume.CUBIC_FEET,
    UnitOfVolume.CUBIC_METERS,
    UnitOfVolume.GALLONS,
    UnitOfVolume.LITERS,
    UnitOfVolume.MILLE_CUBIC_FEET,
}
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


@dataclass(slots=True)
class SourceAdapter:
    """Adapter to allow sources and their flows to be used as sensors."""

    source_type: Literal["grid", "gas", "water"]
    flow_type: Literal["flow_from", "flow_to"] | None
    stat_energy_key: Literal["stat_energy_from", "stat_energy_to"]
    total_money_key: Literal["stat_cost", "stat_compensation"]
    name_suffix: str
    entity_id_suffix: str


SOURCE_ADAPTERS: Final = (
    # Grid import cost (unified format)
    SourceAdapter(
        "grid",
        None,  # No flow_type - unified format
        "stat_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
    SourceAdapter(
        "gas",
        None,
        "stat_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
    SourceAdapter(
        "water",
        None,
        "stat_energy_from",
        "stat_cost",
        "Cost",
        "cost",
    ),
)

# Separate adapter for grid export compensation (needs different price field)
GRID_EXPORT_ADAPTER: Final = SourceAdapter(
    "grid",
    None,  # No flow_type - unified format
    "stat_energy_to",
    "stat_compensation",
    "Compensation",
    "compensation",
)


class EntityNotFoundError(HomeAssistantError):
    """When a referenced entity was not found."""


class SensorManager:
    """Class to handle creation/removal of sensor data."""

    def __init__(
        self, manager: EnergyManager, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize sensor manager."""
        self.manager = manager
        self.async_add_entities = async_add_entities
        self.current_entities: dict[tuple[str, str | None, str], EnergyCostSensor] = {}
        self.current_power_entities: dict[str, EnergyPowerSensor] = {}

    async def async_start(self) -> None:
        """Start."""
        self.manager.async_listen_updates(self._process_manager_data)

        if self.manager.data:
            await self._process_manager_data()

    async def _process_manager_data(self) -> None:
        """Process manager data."""
        to_add: list[EnergyCostSensor | EnergyPowerSensor] = []
        to_remove = dict(self.current_entities)
        power_to_remove = dict(self.current_power_entities)

        async def finish() -> None:
            if to_add:
                self.async_add_entities(to_add)
                await asyncio.wait(ent.add_finished for ent in to_add)

            for key, entity in to_remove.items():
                self.current_entities.pop(key)
                await entity.async_remove()

            for power_key, power_entity in power_to_remove.items():
                self.current_power_entities.pop(power_key)
                await power_entity.async_remove()

        # This guard is for the optional typing of EnergyManager.data.
        # In practice, data is always set to default preferences in async_update
        # before listeners are called, so this case should never happen.
        if not self.manager.data:
            await finish()
            return

        for energy_source in self.manager.data["energy_sources"]:
            for adapter in SOURCE_ADAPTERS:
                if adapter.source_type != energy_source["type"]:
                    continue

                self._process_sensor_data(
                    adapter,
                    energy_source,
                    to_add,
                    to_remove,
                )

            # Handle grid export compensation (unified format uses different price fields)
            if energy_source["type"] == "grid":
                self._process_grid_export_sensor(
                    energy_source,
                    to_add,
                    to_remove,
                )

            # Process power sensors for battery and grid sources
            self._process_power_sensor_data(
                energy_source,
                to_add,
                power_to_remove,
            )

        await finish()

    @callback
    def _process_sensor_data(
        self,
        adapter: SourceAdapter,
        config: Mapping[str, Any],
        to_add: list[EnergyCostSensor | EnergyPowerSensor],
        to_remove: dict[tuple[str, str | None, str], EnergyCostSensor],
    ) -> None:
        """Process sensor data."""
        # No need to create an entity if we already have a cost stat
        if config.get(adapter.total_money_key) is not None:
            return

        # Skip if the energy stat is not configured (e.g., export-only or power-only grids)
        stat_energy = config.get(adapter.stat_energy_key)
        if not stat_energy:
            return

        key = (adapter.source_type, adapter.flow_type, stat_energy)

        # Make sure the right data is there
        # If the entity existed, we don't pop it from to_remove so it's removed
        if not valid_entity_id(stat_energy) or (
            config.get("entity_energy_price") is None
            and config.get("number_energy_price") is None
        ):
            return

        if current_entity := to_remove.pop(key, None):
            current_entity.update_config(config)
            return

        self.current_entities[key] = EnergyCostSensor(
            adapter,
            config,
        )
        to_add.append(self.current_entities[key])

    @callback
    def _process_grid_export_sensor(
        self,
        config: Mapping[str, Any],
        to_add: list[EnergyCostSensor | EnergyPowerSensor],
        to_remove: dict[tuple[str, str | None, str], EnergyCostSensor],
    ) -> None:
        """Process grid export compensation sensor (unified format).

        The unified grid format uses different field names for export pricing:
        - entity_energy_price_export instead of entity_energy_price
        - number_energy_price_export instead of number_energy_price
        """
        # No export meter configured
        stat_energy_to = config.get("stat_energy_to")
        if stat_energy_to is None:
            return

        # Already have a compensation stat
        if config.get("stat_compensation") is not None:
            return

        key = ("grid", None, stat_energy_to)

        # Check for export pricing fields (different names in unified format)
        if not valid_entity_id(stat_energy_to) or (
            config.get("entity_energy_price_export") is None
            and config.get("number_energy_price_export") is None
        ):
            return

        # Create a config wrapper that maps the sell price fields to standard names
        # so EnergyCostSensor can use them
        export_config: dict[str, Any] = {
            "stat_energy_to": stat_energy_to,
            "stat_compensation": config.get("stat_compensation"),
            "entity_energy_price": config.get("entity_energy_price_export"),
            "number_energy_price": config.get("number_energy_price_export"),
        }

        if current_entity := to_remove.pop(key, None):
            current_entity.update_config(export_config)
            return

        self.current_entities[key] = EnergyCostSensor(
            GRID_EXPORT_ADAPTER,
            export_config,
        )
        to_add.append(self.current_entities[key])

    @callback
    def _process_power_sensor_data(
        self,
        energy_source: Mapping[str, Any],
        to_add: list[EnergyCostSensor | EnergyPowerSensor],
        to_remove: dict[str, EnergyPowerSensor],
    ) -> None:
        """Process power sensor data for battery and grid sources."""
        source_type = energy_source.get("type")

        if source_type in ("battery", "grid"):
            # Both battery and grid now use unified format with power_config at top level
            power_config = energy_source.get("power_config")
            if power_config and self._needs_power_sensor(power_config):
                self._create_or_keep_power_sensor(
                    source_type, power_config, to_add, to_remove
                )

    @staticmethod
    def _needs_power_sensor(power_config: PowerConfig) -> bool:
        """Check if power_config needs a transform sensor."""
        # Only create sensors for inverted or two-sensor configs
        # Standard stat_rate configs don't need a transform sensor
        return "stat_rate_inverted" in power_config or (
            "stat_rate_from" in power_config and "stat_rate_to" in power_config
        )

    def _create_or_keep_power_sensor(
        self,
        source_type: str,
        power_config: PowerConfig,
        to_add: list[EnergyCostSensor | EnergyPowerSensor],
        to_remove: dict[str, EnergyPowerSensor],
    ) -> None:
        """Create a power sensor or keep an existing one."""
        unique_id = generate_power_sensor_unique_id(source_type, power_config)

        # If entity already exists, keep it
        if unique_id in to_remove:
            to_remove.pop(unique_id)
            return

        sensor = EnergyPowerSensor(
            source_type,
            power_config,
            unique_id,
            generate_power_sensor_entity_id(source_type, power_config),
        )
        self.current_power_entities[unique_id] = sensor
        to_add.append(sensor)


def _set_result_unless_done(future: asyncio.Future[None]) -> None:
    """Set the result of a future unless it is done."""
    if not future.done():
        future.set_result(None)


class EnergyCostSensor(SensorEntity):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.

    Expected config fields (from adapter or export_config wrapper):
    - stat_energy_key (via adapter): Key to get the energy statistic ID
    - total_money_key (via adapter): Key to get the existing cost/compensation stat
    - entity_energy_price: Entity ID providing price per unit (e.g., $/kWh)
    - number_energy_price: Fixed price per unit

    Note: For grid export compensation, the unified format uses different field names
    (entity_energy_price_export, number_energy_price_export). The _process_grid_export_sensor
    method in SensorManager creates a wrapper config that maps these to the standard
    field names (entity_energy_price, number_energy_price) so this class can use them.
    """

    _attr_entity_registry_visible_default = False
    _attr_should_poll = False

    _wrong_state_class_reported = False
    _wrong_unit_reported = False

    def __init__(
        self,
        adapter: SourceAdapter,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._adapter = adapter
        self.entity_id = f"{config[adapter.stat_energy_key]}_{adapter.entity_id_suffix}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._config = config
        self._last_energy_sensor_state: State | None = None
        # add_finished is set when either of async_added_to_hass or add_to_platform_abort
        # is called
        self.add_finished: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )

    def _reset(self, energy_state: State) -> None:
        """Reset the cost sensor."""
        self._attr_native_value = 0.0
        self._attr_last_reset = dt_util.utcnow()
        self._last_energy_sensor_state = energy_state
        self.async_write_ha_state()

    @callback
    def _update_cost(self) -> None:
        """Update incurred costs."""
        if self._adapter.source_type == "grid":
            valid_units = VALID_ENERGY_UNITS
            default_price_unit: str | None = UnitOfEnergy.KILO_WATT_HOUR

        elif self._adapter.source_type == "gas":
            valid_units = VALID_ENERGY_UNITS_GAS
            # No conversion for gas.
            default_price_unit = None

        elif self._adapter.source_type == "water":
            valid_units = VALID_VOLUME_UNITS_WATER
            if self.hass.config.units is METRIC_SYSTEM:
                default_price_unit = UnitOfVolume.CUBIC_METERS
            else:
                default_price_unit = UnitOfVolume.GALLONS

        energy_state = self.hass.states.get(
            cast(str, self._config[self._adapter.stat_energy_key])
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

        # last_reset must be set if the sensor is SensorStateClass.MEASUREMENT
        if (
            state_class == SensorStateClass.MEASUREMENT
            and ATTR_LAST_RESET not in energy_state.attributes
        ):
            return

        try:
            energy = float(energy_state.state)
        except ValueError:
            return

        try:
            energy_price, energy_price_unit = self._get_energy_price(
                valid_units, default_price_unit
            )
        except EntityNotFoundError:
            return
        except ValueError:
            energy_price = None

        if self._last_energy_sensor_state is None:
            # Initialize as it's the first time all required entities are in place or
            # only the price is missing. In the later case, cost will update the first
            # time the energy is updated after the price entity is in place.
            self._reset(energy_state)
            return

        if energy_price is None:
            return

        energy_unit: str | None = energy_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if energy_unit is None or energy_unit not in valid_units:
            if not self._wrong_unit_reported:
                self._wrong_unit_reported = True
                _LOGGER.warning(
                    "Found unexpected unit %s for %s",
                    energy_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                    energy_state.entity_id,
                )
            return

        if (
            state_class != SensorStateClass.TOTAL_INCREASING
            and energy_state.attributes.get(ATTR_LAST_RESET)
            != self._last_energy_sensor_state.attributes.get(ATTR_LAST_RESET)
        ) or (
            state_class == SensorStateClass.TOTAL_INCREASING
            and reset_detected(
                self.hass,
                cast(str, self._config[self._adapter.stat_energy_key]),
                energy,
                float(self._last_energy_sensor_state.state),
                self._last_energy_sensor_state,
            )
        ):
            # Energy meter was reset, reset cost sensor too
            energy_state_copy = copy.copy(energy_state)
            energy_state_copy.state = "0.0"
            self._reset(energy_state_copy)

        # Update with newly incurred cost
        old_energy_value = float(self._last_energy_sensor_state.state)
        cur_value = cast(float, self._attr_native_value)

        converted_energy_price = self._convert_energy_price(
            energy_price, energy_price_unit, energy_unit
        )

        self._attr_native_value = (
            cur_value + (energy - old_energy_value) * converted_energy_price
        )

        self._last_energy_sensor_state = energy_state

    def _get_energy_price(
        self, valid_units: set[str], default_unit: str | None
    ) -> tuple[float, str | None]:
        """Get the energy price.

        Raises:
            EntityNotFoundError: When the energy price entity is not found.
            ValueError: When the entity state is not a valid float.

        """

        if self._config["entity_energy_price"] is None:
            return cast(float, self._config["number_energy_price"]), default_unit

        energy_price_state = self.hass.states.get(self._config["entity_energy_price"])
        if energy_price_state is None:
            raise EntityNotFoundError

        energy_price = float(energy_price_state.state)

        energy_price_unit: str | None = energy_price_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT, ""
        ).partition("/")[2]

        # For backwards compatibility we don't validate the unit of the price
        # If it is not valid, we assume it's our default price unit.
        if energy_price_unit not in valid_units:
            energy_price_unit = default_unit

        return energy_price, energy_price_unit

    def _convert_energy_price(
        self, energy_price: float, energy_price_unit: str | None, energy_unit: str
    ) -> float:
        """Convert the energy price to the correct unit."""
        if energy_price_unit is None:
            return energy_price

        converter: Callable[[float, str, str], float]
        if energy_unit in VALID_ENERGY_UNITS:
            converter = unit_conversion.EnergyConverter.convert
        else:
            converter = unit_conversion.VolumeConverter.convert

        return converter(energy_price, energy_unit, energy_price_unit)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        energy_state = self.hass.states.get(self._config[self._adapter.stat_energy_key])
        if energy_state:
            name = energy_state.name
        else:
            name = split_entity_id(self._config[self._adapter.stat_energy_key])[
                0
            ].replace("_", " ")

        self._attr_name = f"{name} {self._adapter.name_suffix}"

        self._update_cost()

        # Store stat ID in hass.data so frontend can look it up
        self.hass.data[DOMAIN]["cost_sensors"][
            self._config[self._adapter.stat_energy_key]
        ] = self.entity_id

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                cast(str, self._config[self._adapter.stat_energy_key]),
                self._async_state_changed_listener,
            )
        )
        _set_result_unless_done(self.add_finished)

    @callback
    def _async_state_changed_listener(self, *_: Any) -> None:
        """Handle child updates."""
        self._update_cost()
        self.async_write_ha_state()

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        _set_result_unless_done(self.add_finished)
        super().add_to_platform_abort()

    async def async_will_remove_from_hass(self) -> None:
        """Handle removing from hass."""
        self.hass.data[DOMAIN]["cost_sensors"].pop(
            self._config[self._adapter.stat_energy_key]
        )
        await super().async_will_remove_from_hass()

    @callback
    def update_config(self, config: Mapping[str, Any]) -> None:
        """Update the config."""
        self._config = config

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self.hass.config.currency

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the sensor."""
        entity_registry = er.async_get(self.hass)
        if registry_entry := entity_registry.async_get(
            self._config[self._adapter.stat_energy_key]
        ):
            prefix = registry_entry.id
        else:
            prefix = self._config[self._adapter.stat_energy_key]

        return f"{prefix}_{self._adapter.source_type}_{self._adapter.entity_id_suffix}"


class EnergyPowerSensor(SensorEntity):
    """Transform power sensor values (invert or combine two sensors).

    This sensor handles non-standard power sensor configurations for the energy
    dashboard by either inverting polarity or combining two positive sensors.
    """

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        source_type: str,
        config: PowerConfig,
        unique_id: str,
        entity_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._source_type = source_type
        self._config: PowerConfig = config
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._source_sensors: list[str] = []
        self._is_inverted = "stat_rate_inverted" in config
        self._is_combined = "stat_rate_from" in config and "stat_rate_to" in config

        # Determine source sensors
        if self._is_inverted:
            self._source_sensors = [config["stat_rate_inverted"]]
        elif self._is_combined:
            self._source_sensors = [
                config["stat_rate_from"],
                config["stat_rate_to"],
            ]

        # add_finished is set when either async_added_to_hass or add_to_platform_abort
        # is called
        self.add_finished: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._is_inverted:
            source = self.hass.states.get(self._source_sensors[0])
            return source is not None and source.state not in (
                "unknown",
                "unavailable",
            )
        if self._is_combined:
            discharge = self.hass.states.get(self._source_sensors[0])
            charge = self.hass.states.get(self._source_sensors[1])
            return (
                discharge is not None
                and charge is not None
                and discharge.state not in ("unknown", "unavailable")
                and charge.state not in ("unknown", "unavailable")
            )
        return True

    @callback
    def _update_state(self) -> None:
        """Update the sensor state based on source sensors."""
        if self._is_inverted:
            source_state = self.hass.states.get(self._source_sensors[0])
            if source_state is None or source_state.state in ("unknown", "unavailable"):
                self._attr_native_value = None
                return
            try:
                value = float(source_state.state)
            except ValueError:
                self._attr_native_value = None
                return

            self._attr_native_value = value * -1

        elif self._is_combined:
            discharge_state = self.hass.states.get(self._source_sensors[0])
            charge_state = self.hass.states.get(self._source_sensors[1])

            if (
                discharge_state is None
                or charge_state is None
                or discharge_state.state in ("unknown", "unavailable")
                or charge_state.state in ("unknown", "unavailable")
            ):
                self._attr_native_value = None
                return

            try:
                discharge = float(discharge_state.state)
                charge = float(charge_state.state)
            except ValueError:
                self._attr_native_value = None
                return

            # Get units from state attributes
            discharge_unit = discharge_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            charge_unit = charge_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

            # Convert to Watts if units are present
            if discharge_unit:
                discharge = unit_conversion.PowerConverter.convert(
                    discharge, discharge_unit, UnitOfPower.WATT
                )
            if charge_unit:
                charge = unit_conversion.PowerConverter.convert(
                    charge, charge_unit, UnitOfPower.WATT
                )

            self._attr_native_value = discharge - charge

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        # Set name based on source sensor(s)
        if self._source_sensors:
            entity_reg = er.async_get(self.hass)
            device_id = None
            source_name = None
            # Check first sensor
            if source_entry := entity_reg.async_get(self._source_sensors[0]):
                device_id = source_entry.device_id
                # For combined mode, always use Watts because we may have different source units; for inverted mode, copy source unit
                if self._is_combined:
                    self._attr_native_unit_of_measurement = UnitOfPower.WATT
                else:
                    self._attr_native_unit_of_measurement = (
                        source_entry.unit_of_measurement
                    )
                # Get source name from registry
                source_name = source_entry.name or source_entry.original_name
            # Assign power sensor to same device as source sensor(s)
            # Note: We use manual entity registry update instead of _attr_device_info
            # because device assignment depends on runtime information from the entity
            # registry (which source sensor has a device). This information isn't
            # available during __init__, and the entity is already registered before
            # async_added_to_hass runs, making the standard _attr_device_info pattern
            # incompatible with this use case.
            # If first sensor has no device and we have a second sensor, check it
            if not device_id and len(self._source_sensors) > 1:
                if source_entry := entity_reg.async_get(self._source_sensors[1]):
                    device_id = source_entry.device_id
            # Update entity registry entry with device_id
            if device_id and (power_entry := entity_reg.async_get(self.entity_id)):
                entity_reg.async_update_entity(
                    power_entry.entity_id, device_id=device_id
                )
            else:
                self._attr_has_entity_name = False

            # Set name for inverted mode
            if self._is_inverted:
                if source_name:
                    self._attr_name = f"{source_name} Inverted"
                else:
                    # Fall back to entity_id if no name in registry
                    sensor_name = split_entity_id(self._source_sensors[0])[1].replace(
                        "_", " "
                    )
                    self._attr_name = f"{sensor_name.title()} Inverted"

        # Set name for combined mode
        if self._is_combined:
            self._attr_name = f"{self._source_type.title()} Power"

        self._update_state()

        # Track state changes on all source sensors
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._source_sensors,
                self._async_state_changed_listener,
            )
        )
        _set_result_unless_done(self.add_finished)

    @callback
    def _async_state_changed_listener(self, *_: Any) -> None:
        """Handle source sensor state changes."""
        self._update_state()
        self.async_write_ha_state()

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        _set_result_unless_done(self.add_finished)
        super().add_to_platform_abort()
