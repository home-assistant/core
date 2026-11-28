"""Helper sensor for calculating utility costs."""

import asyncio
from collections.abc import Mapping
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import Any, Final, Literal, Self, cast, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityCapabilityAttribute,
    SensorEntityStateAttribute,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import reset_detected  # pylint: disable=home-assistant-component-root-import
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    EntityStateAttribute,
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify, unit_conversion
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import BATTERY_CHARGE_DIRECTIONS, BATTERY_DIRECTIONS, DOMAIN
from .data import EnergyManager, FixedCostType, PowerConfig, async_get_manager
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
    sensor_manager = SensorManager(
        hass, await async_get_manager(hass), async_add_entities
    )
    await sensor_manager.async_start()


@dataclass(slots=True)
class SourceAdapter:
    """Adapter to allow sources and their flows to be used as sensors."""

    source_type: Literal["grid", "gas", "water"]
    flow_type: Literal["flow_from", "flow_to"] | None
    stat_energy_key: Literal["stat_energy_from", "stat_energy_to"]
    total_money_key: Literal["stat_cost", "stat_compensation"]
    translation_key: str
    entity_id_suffix: str


SOURCE_ADAPTERS: Final = (
    # Grid import cost (unified format)
    SourceAdapter(
        "grid",
        None,  # No flow_type - unified format
        "stat_energy_from",
        "stat_cost",
        "cost",
        "cost",
    ),
    SourceAdapter(
        "gas",
        None,
        "stat_energy_from",
        "stat_cost",
        "cost",
        "cost",
    ),
    SourceAdapter(
        "water",
        None,
        "stat_energy_from",
        "stat_cost",
        "cost",
        "cost",
    ),
)

# Separate adapter for grid export compensation (needs different price field)
GRID_EXPORT_ADAPTER: Final = SourceAdapter(
    "grid",
    None,  # No flow_type - unified format
    "stat_energy_to",
    "stat_compensation",
    "compensation",
    "compensation",
)


class EntityNotFoundError(HomeAssistantError):
    """When a referenced entity was not found."""


class PriceUnitMismatchError(HomeAssistantError):
    """When the price unit cannot be converted to the meter unit."""


class SensorManager:
    """Class to handle creation/removal of sensor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: EnergyManager,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize sensor manager."""
        self.hass = hass
        self.manager = manager
        self.async_add_entities = async_add_entities
        self.current_entities: dict[tuple[str, str | None, str], EnergyCostSensor] = {}
        self.current_power_entities: dict[str, EnergyPowerSensor] = {}
        self.current_fixed_cost_entities: dict[str, EnergyFixedCostSensor] = {}

    async def async_start(self) -> None:
        """Start."""
        self.manager.async_listen_updates(self._process_manager_data)

        if self.manager.data:
            await self._process_manager_data()

    async def _process_manager_data(self) -> None:
        """Process manager data."""
        to_add: list[_ManagedSensor] = []
        to_remove = dict(self.current_entities)
        power_to_remove = dict(self.current_power_entities)
        fixed_cost_to_remove = dict(self.current_fixed_cost_entities)

        async def finish() -> None:
            if to_add:
                self.async_add_entities(to_add)
                await asyncio.wait(ent.add_finished for ent in to_add)

            for key, entity in to_remove.items():
                self.current_entities.pop(key)
                await _async_remove_if_added(entity)

            for power_key, power_entity in power_to_remove.items():
                self.current_power_entities.pop(power_key)
                await _async_remove_if_added(power_entity)

            for fixed_cost_id, fixed_cost_entity in fixed_cost_to_remove.items():
                self.current_fixed_cost_entities.pop(fixed_cost_id)
                await self._async_remove_fixed_cost_sensor(fixed_cost_entity)

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

            # Handle grid export compensation
            # (unified format uses different price fields)
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

        for fixed_cost in self.manager.data.get("fixed_costs", []):
            if (sensor := fixed_cost_to_remove.pop(fixed_cost["id"], None)) is not None:
                sensor.update_config(fixed_cost)
                continue
            sensor = EnergyFixedCostSensor(fixed_cost)
            self.current_fixed_cost_entities[fixed_cost["id"]] = sensor
            to_add.append(sensor)

        await finish()

    @callback
    def _process_sensor_data(
        self,
        adapter: SourceAdapter,
        config: Mapping[str, Any],
        to_add: list[_ManagedSensor],
        to_remove: dict[tuple[str, str | None, str], EnergyCostSensor],
    ) -> None:
        """Process sensor data."""
        # No need to create an entity if we already have a cost stat
        if config.get(adapter.total_money_key) is not None:
            return

        # Skip if the energy stat is not configured
        # (e.g., export-only or power-only grids)
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
        to_add: list[_ManagedSensor],
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
        to_add: list[_ManagedSensor],
        to_remove: dict[str, EnergyPowerSensor],
    ) -> None:
        """Process power sensor data for battery and grid sources."""
        source_type = energy_source.get("type")

        if source_type in ("battery", "grid"):
            # Both battery and grid now use unified format
            # with power_config at top level
            power_config = energy_source.get("power_config")
            if power_config and self._needs_power_sensor(power_config):
                self._create_or_keep_power_sensor(
                    source_type, power_config, to_add, to_remove
                )

    @staticmethod
    def _needs_power_sensor(power_config: PowerConfig) -> bool:
        """Check if power_config needs a transform sensor."""
        # Standard stat_rate configs don't need a transform sensor; battery
        # directions do even with one sensor, because charging is negative
        return (
            "stat_rate_inverted" in power_config
            or ("stat_rate_from" in power_config and "stat_rate_to" in power_config)
            or any(power_key in power_config for _, power_key in BATTERY_DIRECTIONS)
        )

    async def _async_remove_fixed_cost_sensor(
        self, entity: EnergyFixedCostSensor
    ) -> None:
        """Remove the sensor of a deleted fixed cost, with its registry entry."""
        entity_registry = er.async_get(self.hass)
        if entity_id := entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, cast(str, entity.unique_id)
        ):
            entity_registry.async_remove(entity_id)
        # Wait for it, so the same fixed cost can be added again right away
        if entity.hass is not None:
            await entity.async_remove(force_remove=True)

    def _create_or_keep_power_sensor(
        self,
        source_type: str,
        power_config: PowerConfig,
        to_add: list[_ManagedSensor],
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


def _name_from_entity_id(entity_id: str) -> str:
    """Return a name for an entity that has none."""
    return split_entity_id(entity_id)[1].replace("_", " ").capitalize()


def _unit_converter(unit: str) -> type[unit_conversion.BaseUnitConverter]:
    """Return the converter for an energy or volume unit."""
    if unit in VALID_ENERGY_UNITS:
        return unit_conversion.EnergyConverter
    return unit_conversion.VolumeConverter


def _set_result_unless_done(future: asyncio.Future[None]) -> None:
    """Set the result of a future unless it is done."""
    if not future.done():
        future.set_result(None)


async def _async_remove_if_added(entity: SensorEntity) -> None:
    """Remove an entity unless the platform rejected it."""
    # add_to_platform_abort clears hass, e.g. for a disabled or duplicate entity
    if entity.hass is not None:
        await entity.async_remove()


@dataclass
class EnergyCostSensorExtraStoredData(SensorExtraStoredData):
    """Data to price the energy used while Home Assistant was stopped."""

    last_energy_sensor_state: State

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the data."""
        data = super().as_dict()
        data["last_energy_sensor_state"] = self.last_energy_sensor_state.as_dict()
        return data

    @classmethod
    @override
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize the data from a dict, if it has the last energy state."""
        if (
            (extra := SensorExtraStoredData.from_dict(restored)) is None
            or not isinstance(
                energy_state_dict := restored.get("last_energy_sensor_state"), dict
            )
            or (last_energy_sensor_state := State.from_dict(energy_state_dict)) is None
        ):
            return None
        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            last_energy_sensor_state,
        )


class EnergyCostSensor(RestoreSensor):
    """Calculate costs incurred by consuming energy.

    This is intended as a fallback for when no specific cost sensor is available for the
    utility.

    Expected config fields (from adapter or export_config wrapper):
    - stat_energy_key (via adapter): Key to get the energy statistic ID
    - total_money_key (via adapter): Key to get the existing cost/compensation stat
    - entity_energy_price: Entity ID providing price per unit (e.g., $/kWh)
    - number_energy_price: Fixed price per unit

    Note: For grid export compensation, the unified format uses
    different field names (entity_energy_price_export,
    number_energy_price_export). The _process_grid_export_sensor
    method in SensorManager creates a wrapper config that maps
    these to the standard field names (entity_energy_price,
    number_energy_price) so this class can use them.
    """

    _attr_entity_registry_visible_default = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    _wrong_state_class_reported = False
    _wrong_unit_reported = False
    _wrong_price_unit_reported = False

    def __init__(
        self,
        adapter: SourceAdapter,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._adapter = adapter
        self.entity_id = f"{config[adapter.stat_energy_key]}_{adapter.entity_id_suffix}"
        self._attr_translation_key = adapter.translation_key
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._config = config
        self._last_energy_sensor_state: State | None = None
        # SensorManager awaits add_finished; async_on_remove resolves it on the
        # abort path too, since add_to_platform_abort fires on-remove callbacks.
        self.add_finished: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        self.async_on_remove(lambda: _set_result_unless_done(self.add_finished))

    @override
    async def async_prepare_to_add_to_hass(self) -> None:
        """Name the sensor after its energy sensor before it is registered."""
        await super().async_prepare_to_add_to_hass()
        energy_entity_id = self._config[self._adapter.stat_energy_key]
        if energy_state := self.hass.states.get(energy_entity_id):
            energy_name = energy_state.name
        else:
            energy_name = _name_from_entity_id(energy_entity_id)
        self._attr_translation_placeholders = {"energy_name": energy_name}

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

        state_class = energy_state.attributes.get(
            SensorEntityCapabilityAttribute.STATE_CLASS
        )
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
            and SensorEntityStateAttribute.LAST_RESET not in energy_state.attributes
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

        energy_unit: str | None = energy_state.attributes.get(
            EntityStateAttribute.UNIT_OF_MEASUREMENT
        )

        if energy_unit is None or energy_unit not in valid_units:
            if not self._wrong_unit_reported:
                self._wrong_unit_reported = True
                _LOGGER.warning(
                    "Found unexpected unit %s for %s",
                    energy_state.attributes.get(
                        EntityStateAttribute.UNIT_OF_MEASUREMENT
                    ),
                    energy_state.entity_id,
                )
            return

        try:
            converted_energy_price = self._convert_energy_price(
                energy_price, energy_price_unit, energy_unit
            )
        except PriceUnitMismatchError:
            if not self._wrong_price_unit_reported:
                self._wrong_price_unit_reported = True
                _LOGGER.warning(
                    "Not updating cost of %s: unit %s does not match price unit"
                    " per %s of %s",
                    energy_state.entity_id,
                    energy_unit,
                    energy_price_unit,
                    self._config["entity_energy_price"],
                )
            return

        last_energy = float(self._last_energy_sensor_state.state)
        last_energy_unit = self._last_energy_sensor_state.attributes.get(
            EntityStateAttribute.UNIT_OF_MEASUREMENT
        )
        if last_energy_unit != energy_unit:
            try:
                last_energy = _unit_converter(energy_unit).convert(
                    last_energy, last_energy_unit, energy_unit
                )
            except HomeAssistantError:
                # Readings in these units can't be compared, start from this one
                self._last_energy_sensor_state = energy_state
                return

        if state_class == SensorStateClass.TOTAL_INCREASING:
            try:
                meter_reset = reset_detected(
                    self.hass,
                    cast(str, self._config[self._adapter.stat_energy_key]),
                    energy,
                    last_energy,
                    self._last_energy_sensor_state,
                )
            except HomeAssistantError:
                # Negative reading, already logged by reset_detected
                return
        else:
            meter_reset = energy_state.attributes.get(
                SensorEntityStateAttribute.LAST_RESET
            ) != self._last_energy_sensor_state.attributes.get(
                SensorEntityStateAttribute.LAST_RESET
            )

        if meter_reset:
            # Energy meter was reset, reset cost sensor too
            energy_state_copy = copy.copy(energy_state)
            energy_state_copy.state = "0.0"
            self._reset(energy_state_copy)
            last_energy = 0.0

        # Update with newly incurred cost
        cur_value = cast(float, self._attr_native_value)

        self._attr_native_value = (
            cur_value + (energy - last_energy) * converted_energy_price
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

        if (entity_energy_price := self._config.get("entity_energy_price")) is None:
            return cast(float, self._config["number_energy_price"]), default_unit

        energy_price_state = self.hass.states.get(entity_energy_price)
        if energy_price_state is None:
            raise EntityNotFoundError

        energy_price = float(energy_price_state.state)

        energy_price_unit: str | None = energy_price_state.attributes.get(
            EntityStateAttribute.UNIT_OF_MEASUREMENT, ""
        ).partition("/")[2]

        # For backwards compatibility we don't validate the unit of the price
        # If it is not valid, we assume it's our default price unit.
        if energy_price_unit not in valid_units:
            energy_price_unit = default_unit

        return energy_price, energy_price_unit

    def _convert_energy_price(
        self, energy_price: float, energy_price_unit: str | None, energy_unit: str
    ) -> float:
        """Convert the energy price to the correct unit.

        Raises:
            PriceUnitMismatchError: When the price unit cannot be converted to
                the meter unit.

        """
        if energy_price_unit is None:
            return energy_price

        converter = _unit_converter(energy_unit)
        if energy_price_unit not in converter.VALID_UNITS:
            raise PriceUnitMismatchError

        return converter.convert(energy_price, energy_unit, energy_price_unit)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        # Start a new cycle from the last priced reading, so the energy used
        # while stopped is priced too
        if (restored := await self.async_get_last_sensor_data()) is not None:
            self._reset(restored.last_energy_sensor_state)

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
        # Leave readings after the shutdown save to the next start
        if self.hass.is_stopping:
            return
        self._update_cost()
        self.async_write_ha_state()

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Update the stat ID stored for the frontend."""
        super().async_entity_id_changed(old_entity_id)
        self.hass.data[DOMAIN]["cost_sensors"][
            self._config[self._adapter.stat_energy_key]
        ] = self.entity_id

    @override
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
    @override
    def extra_restore_state_data(self) -> SensorExtraStoredData:
        """Return the data needed to price the energy used while stopped."""
        # Only the save made while stopping stores the last priced reading.
        # Restore state is also saved every 15 minutes while running. After a
        # crash, the last of those saves holds an older reading, and restoring
        # it would price the energy used since then a second time. A sensor
        # removed by a config change must not price the time it was gone either.
        if self._last_energy_sensor_state is None or not self.hass.is_stopping:
            return super().extra_restore_state_data
        return EnergyCostSensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            self._last_energy_sensor_state,
        )

    @override
    async def async_get_last_sensor_data(
        self,
    ) -> EnergyCostSensorExtraStoredData | None:
        """Return the restored data, if it is complete."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return EnergyCostSensorExtraStoredData.from_dict(
            restored_last_extra_data.as_dict()
        )

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self.hass.config.currency

    @property
    @override
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
    """Transform power sensor values (invert or combine sensors).

    This sensor handles non-standard power sensor configurations for the energy
    dashboard by either inverting polarity or combining positive sensors.
    """

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _wrong_unit_reported = False

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
        # Combined: source sensors with the sign they add to the net power
        self._terms: list[tuple[str, int]] = []
        if "stat_rate_from" in config and "stat_rate_to" in config:
            self._terms = [(config["stat_rate_from"], 1), (config["stat_rate_to"], -1)]
        else:
            self._terms = [
                (config[power_key], -1 if direction in BATTERY_CHARGE_DIRECTIONS else 1)
                for direction in BATTERY_DIRECTIONS
                if (power_key := direction[1]) in config
            ]
        self._is_combined = bool(self._terms)

        # Combined mode always emits Watts because _update_state converts
        # heterogeneous source units to W internally. Inverted mode copies
        # the source unit in _update_state to track source changes.
        if self._is_combined:
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_translation_key = f"{source_type}_power"

        # Determine source sensors
        if self._is_inverted:
            self._source_sensors = [config["stat_rate_inverted"]]
            self._attr_translation_key = "power_inverted"
        elif self._is_combined:
            self._source_sensors = [sensor for sensor, _ in self._terms]

        # SensorManager awaits add_finished; async_on_remove resolves it on the
        # abort path too, since add_to_platform_abort fires on-remove callbacks.
        self.add_finished: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        self.async_on_remove(lambda: _set_result_unless_done(self.add_finished))

    @override
    async def async_prepare_to_add_to_hass(self) -> None:
        """Name the sensor after its source sensor before it is registered."""
        await super().async_prepare_to_add_to_hass()
        if not self._is_inverted:
            return
        source = self._source_sensors[0]
        if not (
            (entry := er.async_get(self.hass).async_get(source))
            and (source_name := entry.name or entry.original_name)
        ):
            source_name = _name_from_entity_id(source)
        self._attr_translation_placeholders = {"source_name": source_name}

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if self._is_inverted:
            source = self.hass.states.get(self._source_sensors[0])
            return source is not None and source.state not in (
                "unknown",
                "unavailable",
            )
        if self._is_combined:
            return all(
                (source := self.hass.states.get(sensor)) is not None
                and source.state not in ("unknown", "unavailable")
                for sensor in self._source_sensors
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

            self._attr_native_unit_of_measurement = source_state.attributes.get(
                EntityStateAttribute.UNIT_OF_MEASUREMENT
            )
            self._attr_native_value = value * -1

        elif self._is_combined:
            source_states: list[State] = []
            for sensor in self._source_sensors:
                source_state = self.hass.states.get(sensor)
                if source_state is None or source_state.state in (
                    "unknown",
                    "unavailable",
                ):
                    self._attr_native_value = None
                    return
                source_states.append(source_state)

            try:
                values = [float(source_state.state) for source_state in source_states]
            except ValueError:
                self._attr_native_value = None
                return

            # Convert to Watts if units are present
            net_power = 0.0
            try:
                for source_state, value, (_, sign) in zip(
                    source_states, values, self._terms, strict=True
                ):
                    if unit := source_state.attributes.get(
                        EntityStateAttribute.UNIT_OF_MEASUREMENT
                    ):
                        value = unit_conversion.PowerConverter.convert(
                            value, unit, UnitOfPower.WATT
                        )
                    net_power += sign * value
            except HomeAssistantError as err:
                if not self._wrong_unit_reported:
                    self._wrong_unit_reported = True
                    _LOGGER.warning(
                        "Unable to combine %s: %s",
                        " and ".join(self._source_sensors),
                        err,
                    )
                self._attr_native_value = None
                return

            self._attr_native_value = net_power

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._source_sensors:
            entity_reg = er.async_get(self.hass)
            # Assign power sensor to the device of the first source sensor
            # that has one
            # Note: We use manual entity registry update instead of _attr_device_info
            # because device assignment depends on runtime information from the entity
            # registry (which source sensor has a device). This information isn't
            # available during __init__, and the entity is already registered before
            # async_added_to_hass runs, making the standard _attr_device_info pattern
            # incompatible with this use case.
            device_id = next(
                (
                    source_entry.device_id
                    for sensor in self._source_sensors
                    if (source_entry := entity_reg.async_get(sensor))
                    and source_entry.device_id
                ),
                None,
            )
            # Update entity registry entry with device_id
            if device_id and (power_entry := entity_reg.async_get(self.entity_id)):
                entity_reg.async_update_entity(
                    power_entry.entity_id, device_id=device_id
                )
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


def _period_start(now: datetime, period: str) -> datetime:
    """Return the local start of the period that contains now."""
    day = dt_util.as_local(now).date()
    if period == "month":
        day = day.replace(day=1)
    elif period == "year":
        day = day.replace(month=1, day=1)
    return dt_util.start_of_local_day(day)


def _next_period_start(start: datetime, period: str) -> datetime:
    """Return the local start of the period after the one that contains start."""
    day = dt_util.as_local(start).date()
    if period == "day":
        day += timedelta(days=1)
    elif period == "month":
        day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        day = day.replace(year=day.year + 1, month=1, day=1)
    return dt_util.start_of_local_day(day)


def _previous_period_start(start: datetime, period: str) -> datetime:
    """Return the local start of the period before the one that contains start."""
    day = dt_util.as_local(start).date()
    if period == "day":
        day -= timedelta(days=1)
    elif period == "month":
        day = (day.replace(day=1) - timedelta(days=1)).replace(day=1)
    else:
        day = day.replace(year=day.year - 1, month=1, day=1)
    return dt_util.start_of_local_day(day)


def _same_period_in_local_time(start: datetime) -> datetime:
    """Return the start of the same calendar day in the local time zone."""
    return dt_util.start_of_local_day(start.date())


def _parse_restored_datetime(value: Any) -> datetime | None:
    """Parse a restored datetime."""
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


@dataclass
class EnergyFixedCostSensorExtraStoredData(SensorExtraStoredData):
    """Data to continue the total and know which periods are already charged."""

    last_reset: datetime
    last_charged: datetime
    period: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the data."""
        data = super().as_dict()
        data["last_reset"] = self.last_reset.isoformat()
        data["last_charged"] = self.last_charged.isoformat()
        data["period"] = self.period
        return data

    @classmethod
    @override
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize the data from a dict, if it has a total and its periods."""
        if (
            (extra := SensorExtraStoredData.from_dict(restored)) is None
            or not isinstance(extra.native_value, (int, float))
            or (last_reset := _parse_restored_datetime(restored.get("last_reset")))
            is None
            or (last_charged := _parse_restored_datetime(restored.get("last_charged")))
            is None
            or (period := restored.get("period")) not in ("day", "month", "year")
        ):
            return None
        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            last_reset,
            last_charged,
            period,
        )


class EnergyFixedCostSensor(RestoreSensor):
    """Add a fixed cost, like a standing charge, at the start of each period."""

    _attr_entity_registry_visible_default = False
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, config: FixedCostType) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._config = config
        self._attr_unique_id = f"fixed_cost_{config['id']}"
        self._attr_name = config["name"]
        self.entity_id = f"sensor.{slugify(config['name'])}_fixed_cost"
        # The start of the last period that was charged, in the local time zone
        self._last_charged: datetime
        self._unsub_charge: CALLBACK_TYPE | None = None
        self._unsub_amount_entity: CALLBACK_TYPE | None = None
        # SensorManager awaits add_finished; async_on_remove resolves it on the
        # abort path too, since add_to_platform_abort fires on-remove callbacks.
        self.add_finished: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        self.async_on_remove(lambda: _set_result_unless_done(self.add_finished))

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the total and charge the periods that are due."""
        if (restored := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = restored.native_value
            self._attr_last_reset = restored.last_reset
            self._last_charged = _same_period_in_local_time(restored.last_charged)
            if restored.period != self._config["period"]:
                self._async_period_changed(restored.period)
        else:
            # Start a new cycle at 0 instead of dropping a lost total. The first
            # state of a cycle is the zero point of the statistics, so charges
            # are only added after it.
            self._attr_native_value = 0.0
            self._attr_last_reset = dt_util.utcnow()
            # The current period is due
            self._last_charged = _previous_period_start(
                dt_util.utcnow(), self._config["period"]
            )

        self.hass.data[DOMAIN]["fixed_cost_sensors"][self._config["id"]] = (
            self.entity_id
        )
        self._async_track_amount_entity()
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._async_core_config_updated
            )
        )
        self.async_on_remove(self._async_unsubscribe)
        # Runs after the platform writes the restored or zero state
        self._async_schedule_charge(dt_util.utcnow())
        _set_result_unless_done(self.add_finished)

    @callback
    def _async_unsubscribe(self) -> None:
        """Stop the timer and the amount entity listener."""
        if self._unsub_charge is not None:
            self._unsub_charge()
            self._unsub_charge = None
        if self._unsub_amount_entity is not None:
            self._unsub_amount_entity()
            self._unsub_amount_entity = None

    @callback
    def _async_track_amount_entity(self) -> None:
        """Charge a period that is due once the amount entity has a valid state."""
        if self._unsub_amount_entity is not None:
            self._unsub_amount_entity()
            self._unsub_amount_entity = None
        if (entity_id := self._config["entity_amount"]) is not None:
            self._unsub_amount_entity = async_track_state_change_event(
                self.hass, entity_id, self._async_charge
            )

    @callback
    def _async_core_config_updated(self, event: Event) -> None:
        """Move the next charge to the period start in a new time zone."""
        if "time_zone" not in event.data:
            return
        self._last_charged = _same_period_in_local_time(self._last_charged)
        self._async_charge()

    @callback
    def _async_schedule_charge(self, point_in_time: datetime) -> None:
        """Charge the periods that are due at a point in time."""
        if self._unsub_charge is not None:
            self._unsub_charge()
        self._unsub_charge = async_track_point_in_utc_time(
            self.hass, self._async_charge, point_in_time
        )

    def _amount(self) -> float | None:
        """Return the amount to charge per period, if it is known."""
        if (number_amount := self._config["number_amount"]) is not None:
            return number_amount
        if (
            state := self.hass.states.get(cast(str, self._config["entity_amount"]))
        ) is None:
            return None
        currency = self.hass.config.currency
        # The amount is added as is, so it is not charged in any other unit
        if state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT) not in (
            currency,
            f"{currency}/{self._config['period']}",
        ):
            return None
        try:
            amount = float(state.state)
        except ValueError:
            return None
        return amount if math.isfinite(amount) else None

    @callback
    def _async_charge(self, _: Any = None) -> None:
        """Charge every period that started since the last charge."""
        period = self._config["period"]
        current = _period_start(dt_util.utcnow(), period)
        periods = 0
        start = self._last_charged
        while (start := _next_period_start(start, period)) <= current:
            periods += 1
        if periods and (amount := self._amount()) is not None:
            self._attr_native_value = cast(float, self.native_value) + amount * periods
            self._last_charged = current
            self.async_write_ha_state()
        self._async_schedule_charge(_next_period_start(current, period))

    @callback
    def update_config(self, config: FixedCostType) -> None:
        """Update the config."""
        old_config = self._config
        self._config = config
        self._attr_name = config["name"]
        # Only a sensor that is added has a timer, not a disabled one
        if self._unsub_charge is not None:
            self._async_config_changed(old_config)

    @callback
    def _async_config_changed(self, old_config: FixedCostType) -> None:
        """Apply a changed config to the added sensor."""
        if self._config["entity_amount"] != old_config["entity_amount"]:
            self._async_track_amount_entity()
        if (old_period := old_config["period"]) != self._config["period"]:
            self._async_period_changed(old_period)
        self._async_charge()
        self.async_write_ha_state()

    @callback
    def _async_period_changed(self, old_period: str) -> None:
        """Move the last charged period to the new period length."""
        now = dt_util.utcnow()
        period = self._config["period"]
        if self._last_charged >= _period_start(now, old_period):
            # The current period of the new length counts as charged
            self._last_charged = _period_start(now, period)
        else:
            # The amount was not known yet, the current period is still due
            self._last_charged = _previous_period_start(now, period)

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Update the entity ID stored for the frontend."""
        super().async_entity_id_changed(old_entity_id)
        self.hass.data[DOMAIN]["fixed_cost_sensors"][self._config["id"]] = (
            self.entity_id
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Handle removing from hass."""
        self.hass.data[DOMAIN]["fixed_cost_sensors"].pop(self._config["id"])
        await super().async_will_remove_from_hass()

    @property
    @override
    def extra_restore_state_data(self) -> SensorExtraStoredData:
        """Return the total together with its cycle and the last charged period."""
        return EnergyFixedCostSensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            cast(datetime, self.last_reset),
            self._last_charged,
            self._config["period"],
        )

    @override
    async def async_get_last_sensor_data(
        self,
    ) -> EnergyFixedCostSensorExtraStoredData | None:
        """Return the restored data, if it is complete."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return EnergyFixedCostSensorExtraStoredData.from_dict(
            restored_last_extra_data.as_dict()
        )

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self.hass.config.currency


type _ManagedSensor = EnergyCostSensor | EnergyPowerSensor | EnergyFixedCostSensor
