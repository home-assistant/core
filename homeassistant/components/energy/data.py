"""Energy data."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any, Literal, NotRequired, TypedDict

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 3
STORAGE_KEY = DOMAIN


@singleton.singleton(f"{DOMAIN}_manager")
async def async_get_manager(hass: HomeAssistant) -> EnergyManager:
    """Return an initialized data manager."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    return manager


class FlowFromGridSourceType(TypedDict):
    """Dictionary describing the 'from' stat for the grid source."""

    # statistic_id of an energy meter (kWh)
    stat_energy_from: str

    # statistic_id of costs ($) incurred from the energy meter
    # If set to None and entity_energy_price or number_energy_price are configured,
    # an EnergyCostSensor will be automatically created
    stat_cost: str | None

    # Used to generate costs if stat_cost is set to None
    entity_energy_price: str | None  # entity_id of an entity providing price ($/kWh)
    number_energy_price: float | None  # Price for energy ($/kWh)


class FlowToGridSourceType(TypedDict):
    """Dictionary describing the 'to' stat for the grid source."""

    # kWh meter
    stat_energy_to: str

    # statistic_id of compensation ($) received for contributing back
    # If set to None and entity_energy_price or number_energy_price are configured,
    # an EnergyCostSensor will be automatically created
    stat_compensation: str | None

    # Used to generate costs if stat_compensation is set to None
    entity_energy_price: str | None  # entity_id of an entity providing price ($/kWh)
    number_energy_price: float | None  # Price for energy ($/kWh)


class PowerConfig(TypedDict, total=False):
    """Dictionary holding power sensor configuration options.

    Users can configure power sensors in three ways:
    1. Standard: single sensor (positive=discharge/from_grid, negative=charge/to_grid)
    2. Inverted: single sensor with opposite polarity (needs to be multiplied by -1)
    3. Two sensors: separate positive sensors for each direction
    """

    # Standard: single sensor (positive=discharge/from_grid, negative=charge/to_grid)
    stat_rate: str

    # Inverted: single sensor with opposite polarity (needs to be multiplied by -1)
    stat_rate_inverted: str

    # Two sensors: separate positive sensors for each direction
    # Result = stat_rate_from - stat_rate_to (positive when net outflow)
    stat_rate_from: str  # Battery: discharge, Grid: consumption
    stat_rate_to: str  # Battery: charge, Grid: return


class GridPowerSourceType(TypedDict, total=False):
    """Dictionary holding the source of grid power consumption."""

    # statistic_id of a power meter (kW)
    # negative values indicate grid return
    # This is either the original sensor or a generated template sensor
    stat_rate: str

    # User's original power sensor configuration
    power_config: PowerConfig


class LegacyGridSourceType(TypedDict):
    """Legacy dictionary holding the source of grid energy consumption.

    This format is deprecated and will be migrated to GridSourceType.
    """

    type: Literal["grid"]

    flow_from: list[FlowFromGridSourceType]
    flow_to: list[FlowToGridSourceType]
    power: NotRequired[list[GridPowerSourceType]]

    cost_adjustment_day: float


class GridSourceType(TypedDict):
    """Dictionary holding a unified grid connection (like batteries).

    Each grid connection represents a single import/export pair with
    optional power tracking. Multiple grid sources are allowed.
    """

    type: Literal["grid"]

    # Import meter - kWh consumed from grid
    # Can be None for export-only or power-only grids migrated from legacy format
    stat_energy_from: str | None

    # Export meter (optional) - kWh returned to grid (solar/battery export)
    stat_energy_to: str | None

    # Cost tracking for import
    stat_cost: str | None  # statistic_id of costs ($) incurred
    entity_energy_price: str | None  # entity_id providing price ($/kWh)
    number_energy_price: float | None  # Fixed price ($/kWh)

    # Compensation tracking for export
    stat_compensation: str | None  # statistic_id of compensation ($) received
    entity_energy_price_export: str | None  # entity_id providing export price ($/kWh)
    number_energy_price_export: float | None  # Fixed export price ($/kWh)

    # Power measurement (optional)
    # positive when consuming from grid, negative when exporting
    stat_rate: NotRequired[str]
    power_config: NotRequired[PowerConfig]

    cost_adjustment_day: float


class SolarSourceType(TypedDict):
    """Dictionary holding the source of energy production."""

    type: Literal["solar"]

    stat_energy_from: str
    stat_rate: NotRequired[str]
    config_entry_solar_forecast: list[str] | None


class BatterySourceType(TypedDict):
    """Dictionary holding the source of battery storage."""

    type: Literal["battery"]

    stat_energy_from: str
    stat_energy_to: str
    # positive when discharging, negative when charging
    # This is either the original sensor or a generated template sensor
    stat_rate: NotRequired[str]

    # User's original power sensor configuration
    power_config: NotRequired[PowerConfig]


class GasSourceType(TypedDict):
    """Dictionary holding the source of gas consumption."""

    type: Literal["gas"]

    stat_energy_from: str

    # Instantaneous flow rate: m³/h, L/min, etc.
    stat_rate: NotRequired[str]

    # statistic_id of costs ($) incurred from the gas meter
    # If set to None and entity_energy_price or number_energy_price are configured,
    # an EnergyCostSensor will be automatically created
    stat_cost: str | None

    # Used to generate costs if stat_cost is set to None
    entity_energy_price: str | None  # entity_id of an entity providing price ($/m³)
    number_energy_price: float | None  # Price for energy ($/m³)


class WaterSourceType(TypedDict):
    """Dictionary holding the source of water consumption."""

    type: Literal["water"]

    stat_energy_from: str

    # Instantaneous flow rate: L/min, gal/min, m³/h, etc.
    stat_rate: NotRequired[str]

    # statistic_id of costs ($) incurred from the water meter
    # If set to None and entity_energy_price or number_energy_price are configured,
    # an EnergyCostSensor will be automatically created
    stat_cost: str | None

    # Used to generate costs if stat_cost is set to None
    entity_energy_price: str | None  # entity_id of an entity providing price ($/m³)
    number_energy_price: float | None  # Price for energy ($/m³)


type SourceType = (
    GridSourceType
    | SolarSourceType
    | BatterySourceType
    | GasSourceType
    | WaterSourceType
)


class DeviceConsumption(TypedDict):
    """Dictionary holding the source of individual device consumption."""

    # This is an ever increasing value
    stat_consumption: str

    # Instantaneous rate of flow: W, L/min or m³/h
    stat_rate: NotRequired[str]

    # An optional custom name for display in energy graphs
    name: str | None

    # An optional statistic_id identifying a device
    # that includes this device's consumption in its total
    included_in_stat: NotRequired[str]


class EnergyPreferences(TypedDict):
    """Dictionary holding the energy data."""

    energy_sources: list[SourceType]
    device_consumption: list[DeviceConsumption]
    device_consumption_water: NotRequired[list[DeviceConsumption]]


class EnergyPreferencesUpdate(EnergyPreferences, total=False):
    """all types optional."""


def _flow_from_ensure_single_price(
    val: FlowFromGridSourceType,
) -> FlowFromGridSourceType:
    """Ensure we use a single price source."""
    if (
        val["entity_energy_price"] is not None
        and val["number_energy_price"] is not None
    ):
        raise vol.Invalid("Define either an entity or a fixed number for the price")

    return val


FLOW_FROM_GRID_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("stat_energy_from"): str,
            vol.Optional("stat_cost"): vol.Any(str, None),
            # entity_energy_from was removed in HA Core 2022.10
            vol.Remove("entity_energy_from"): vol.Any(str, None),
            vol.Optional("entity_energy_price"): vol.Any(str, None),
            vol.Optional("number_energy_price"): vol.Any(vol.Coerce(float), None),
        }
    ),
    _flow_from_ensure_single_price,
)


FLOW_TO_GRID_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("stat_energy_to"): str,
        vol.Optional("stat_compensation"): vol.Any(str, None),
        # entity_energy_to was removed in HA Core 2022.10
        vol.Remove("entity_energy_to"): vol.Any(str, None),
        vol.Optional("entity_energy_price"): vol.Any(str, None),
        vol.Optional("number_energy_price"): vol.Any(vol.Coerce(float), None),
    }
)


def _validate_power_config(val: dict[str, Any]) -> dict[str, Any]:
    """Validate power_config has exactly one configuration method."""
    if not val:
        raise vol.Invalid("power_config must have at least one option")

    # Ensure only one configuration method is used
    has_single = "stat_rate" in val
    has_inverted = "stat_rate_inverted" in val
    has_combined = "stat_rate_from" in val

    methods_count = sum([has_single, has_inverted, has_combined])
    if methods_count > 1:
        raise vol.Invalid(
            "power_config must use only one configuration method: "
            "stat_rate, stat_rate_inverted, or stat_rate_from/stat_rate_to"
        )

    return val


POWER_CONFIG_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive("stat_rate", "power_source"): str,
            vol.Exclusive("stat_rate_inverted", "power_source"): str,
            # stat_rate_from/stat_rate_to: two sensors for bidirectional power
            # Battery: from=discharge (out), to=charge (in)
            # Grid: from=consumption, to=return
            vol.Inclusive("stat_rate_from", "two_sensors"): str,
            vol.Inclusive("stat_rate_to", "two_sensors"): str,
        }
    ),
    _validate_power_config,
)


GRID_POWER_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        {
            # stat_rate and power_config are both optional schema keys, but the validator
            # requires that at least one is provided; power_config takes precedence
            vol.Optional("stat_rate"): str,
            vol.Optional("power_config"): POWER_CONFIG_SCHEMA,
        }
    ),
    cv.has_at_least_one_key("stat_rate", "power_config"),
)


def _generate_unique_value_validator(key: str) -> Callable[[list[dict]], list[dict]]:
    """Generate a validator that ensures a value is only used once."""

    def validate_uniqueness(
        val: list[dict],
    ) -> list[dict]:
        """Ensure that the user doesn't add duplicate values."""
        counts = Counter(item.get(key) for item in val if item.get(key) is not None)

        for value, count in counts.items():
            if count > 1:
                raise vol.Invalid(f"Cannot specify {value} more than once")

        return val

    return validate_uniqueness


def _grid_ensure_single_price_import(
    val: dict[str, Any],
) -> dict[str, Any]:
    """Ensure we use a single price source for import."""
    if (
        val.get("entity_energy_price") is not None
        and val.get("number_energy_price") is not None
    ):
        raise vol.Invalid("Define either an entity or a fixed number for import price")
    return val


def _grid_ensure_single_price_export(
    val: dict[str, Any],
) -> dict[str, Any]:
    """Ensure we use a single price source for export."""
    if (
        val.get("entity_energy_price_export") is not None
        and val.get("number_energy_price_export") is not None
    ):
        raise vol.Invalid("Define either an entity or a fixed number for export price")
    return val


def _grid_ensure_at_least_one_stat(
    val: dict[str, Any],
) -> dict[str, Any]:
    """Ensure at least one of import, export, or power is configured."""
    if (
        val.get("stat_energy_from") is None
        and val.get("stat_energy_to") is None
        and val.get("stat_rate") is None
        and val.get("power_config") is None
    ):
        raise vol.Invalid(
            "Grid must have at least one of: import meter, export meter, or power sensor"
        )
    return val


GRID_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("type"): "grid",
            # Import meter (can be None for export-only grids from legacy migration)
            vol.Optional("stat_energy_from", default=None): vol.Any(str, None),
            # Export meter (optional)
            vol.Optional("stat_energy_to", default=None): vol.Any(str, None),
            # Import cost tracking
            vol.Optional("stat_cost", default=None): vol.Any(str, None),
            vol.Optional("entity_energy_price", default=None): vol.Any(str, None),
            vol.Optional("number_energy_price", default=None): vol.Any(
                vol.Coerce(float), None
            ),
            # Export compensation tracking
            vol.Optional("stat_compensation", default=None): vol.Any(str, None),
            vol.Optional("entity_energy_price_export", default=None): vol.Any(
                str, None
            ),
            vol.Optional("number_energy_price_export", default=None): vol.Any(
                vol.Coerce(float), None
            ),
            # Power measurement (optional)
            vol.Optional("stat_rate"): str,
            vol.Optional("power_config"): POWER_CONFIG_SCHEMA,
            vol.Required("cost_adjustment_day"): vol.Coerce(float),
        }
    ),
    _grid_ensure_single_price_import,
    _grid_ensure_single_price_export,
    _grid_ensure_at_least_one_stat,
)
SOLAR_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "solar",
        vol.Required("stat_energy_from"): str,
        vol.Optional("stat_rate"): str,
        vol.Optional("config_entry_solar_forecast"): vol.Any([str], None),
    }
)
BATTERY_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "battery",
        vol.Required("stat_energy_from"): str,
        vol.Required("stat_energy_to"): str,
        # Both stat_rate and power_config are optional
        # If power_config is provided, it takes precedence and stat_rate is overwritten
        vol.Optional("stat_rate"): str,
        vol.Optional("power_config"): POWER_CONFIG_SCHEMA,
    }
)
GAS_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "gas",
        vol.Required("stat_energy_from"): str,
        vol.Optional("stat_rate"): str,
        vol.Optional("stat_cost"): vol.Any(str, None),
        # entity_energy_from was removed in HA Core 2022.10
        vol.Remove("entity_energy_from"): vol.Any(str, None),
        vol.Optional("entity_energy_price"): vol.Any(str, None),
        vol.Optional("number_energy_price"): vol.Any(vol.Coerce(float), None),
    }
)
WATER_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "water",
        vol.Required("stat_energy_from"): str,
        vol.Optional("stat_rate"): str,
        vol.Optional("stat_cost"): vol.Any(str, None),
        vol.Optional("entity_energy_price"): vol.Any(str, None),
        vol.Optional("number_energy_price"): vol.Any(vol.Coerce(float), None),
    }
)


def check_type_limits(value: list[SourceType]) -> list[SourceType]:
    """Validate that we don't have too many of certain types."""
    # Currently no type limits - multiple grid sources are allowed (like batteries)
    return value


def _validate_grid_stat_uniqueness(value: list[SourceType]) -> list[SourceType]:
    """Validate that grid statistics are unique across all sources."""
    seen_import: set[str] = set()
    seen_export: set[str] = set()
    seen_rate: set[str] = set()

    for source in value:
        if source.get("type") != "grid":
            continue

        # Cast to GridSourceType since we've filtered for grid type
        grid_source: GridSourceType = source  # type: ignore[assignment]

        # Check import meter uniqueness
        if (stat_from := grid_source.get("stat_energy_from")) is not None:
            if stat_from in seen_import:
                raise vol.Invalid(
                    f"Import meter {stat_from} is used in multiple grid connections"
                )
            seen_import.add(stat_from)

        # Check export meter uniqueness
        if (stat_to := grid_source.get("stat_energy_to")) is not None:
            if stat_to in seen_export:
                raise vol.Invalid(
                    f"Export meter {stat_to} is used in multiple grid connections"
                )
            seen_export.add(stat_to)

        # Check power stat uniqueness
        if (stat_rate := grid_source.get("stat_rate")) is not None:
            if stat_rate in seen_rate:
                raise vol.Invalid(
                    f"Power stat {stat_rate} is used in multiple grid connections"
                )
            seen_rate.add(stat_rate)

    return value


ENERGY_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        [
            cv.key_value_schemas(
                "type",
                {
                    "grid": GRID_SOURCE_SCHEMA,
                    "solar": SOLAR_SOURCE_SCHEMA,
                    "battery": BATTERY_SOURCE_SCHEMA,
                    "gas": GAS_SOURCE_SCHEMA,
                    "water": WATER_SOURCE_SCHEMA,
                },
            )
        ]
    ),
    check_type_limits,
    _validate_grid_stat_uniqueness,
)

DEVICE_CONSUMPTION_SCHEMA = vol.Schema(
    {
        vol.Required("stat_consumption"): str,
        vol.Optional("stat_rate"): str,
        vol.Optional("name"): str,
        vol.Optional("included_in_stat"): str,
    }
)


def _migrate_legacy_grid_to_unified(
    old_grid: dict[str, Any],
) -> list[dict[str, Any]]:
    """Migrate legacy grid format (flow_from/flow_to/power arrays) to unified format.

    Each grid connection can have any combination of import, export, and power -
    all are optional as long as at least one is configured.

    Migration pairs arrays by index position:
    - flow_from[i], flow_to[i], and power[i] combine into grid connection i
    - If arrays have different lengths, missing entries get None for that field
    - The number of grid connections equals max(len(flow_from), len(flow_to), len(power))
    """
    flow_from = old_grid.get("flow_from", [])
    flow_to = old_grid.get("flow_to", [])
    power_list = old_grid.get("power", [])
    cost_adj = old_grid.get("cost_adjustment_day", 0.0)

    new_sources: list[dict[str, Any]] = []
    # Number of grid connections = max length across all three arrays
    # If all arrays are empty, don't create any grid sources
    max_len = max(len(flow_from), len(flow_to), len(power_list))
    if max_len == 0:
        return []

    for i in range(max_len):
        source: dict[str, Any] = {
            "type": "grid",
            "cost_adjustment_day": cost_adj,
        }

        # Import fields from flow_from
        if i < len(flow_from):
            ff = flow_from[i]
            source["stat_energy_from"] = ff.get("stat_energy_from") or None
            source["stat_cost"] = ff.get("stat_cost")
            source["entity_energy_price"] = ff.get("entity_energy_price")
            source["number_energy_price"] = ff.get("number_energy_price")
        else:
            # Export-only entry - set import to None (validation will flag this)
            source["stat_energy_from"] = None
            source["stat_cost"] = None
            source["entity_energy_price"] = None
            source["number_energy_price"] = None

        # Export fields from flow_to
        if i < len(flow_to):
            ft = flow_to[i]
            source["stat_energy_to"] = ft.get("stat_energy_to")
            source["stat_compensation"] = ft.get("stat_compensation")
            source["entity_energy_price_export"] = ft.get("entity_energy_price")
            source["number_energy_price_export"] = ft.get("number_energy_price")
        else:
            source["stat_energy_to"] = None
            source["stat_compensation"] = None
            source["entity_energy_price_export"] = None
            source["number_energy_price_export"] = None

        # Power config at index i goes to grid connection at index i
        if i < len(power_list):
            power = power_list[i]
            if "power_config" in power:
                source["power_config"] = power["power_config"]
            if "stat_rate" in power:
                source["stat_rate"] = power["stat_rate"]

        new_sources.append(source)

    return new_sources


def _is_legacy_grid_format(source: dict[str, Any]) -> bool:
    """Check if a grid source is in the legacy format."""
    return source.get("type") == "grid" and "flow_from" in source


class _EnergyPreferencesStore(storage.Store[EnergyPreferences]):
    """Energy preferences store with migration support."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        data = old_data
        if old_major_version == 1 and old_minor_version < 2:
            # Add device_consumption_water field if it doesn't exist
            data.setdefault("device_consumption_water", [])

        if old_major_version == 1 and old_minor_version < 3:
            # Migrate legacy grid format to unified format
            new_sources: list[dict[str, Any]] = []
            for source in data.get("energy_sources", []):
                if _is_legacy_grid_format(source):
                    # Convert legacy grid to multiple unified grid sources
                    new_sources.extend(_migrate_legacy_grid_to_unified(source))
                else:
                    new_sources.append(source)
            data["energy_sources"] = new_sources

        return data


class EnergyManager:
    """Manage the instance energy prefs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize energy manager."""
        self._hass = hass
        self._store = _EnergyPreferencesStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
        )
        self.data: EnergyPreferences | None = None
        self._update_listeners: list[Callable[[], Awaitable]] = []

    async def async_initialize(self) -> None:
        """Initialize the energy integration."""
        self.data = await self._store.async_load()

    @staticmethod
    def default_preferences() -> EnergyPreferences:
        """Return default preferences."""
        return {
            "energy_sources": [],
            "device_consumption": [],
            "device_consumption_water": [],
        }

    async def async_update(self, update: EnergyPreferencesUpdate) -> None:
        """Update the preferences."""
        if self.data is None:
            data = EnergyManager.default_preferences()
        else:
            data = self.data.copy()

        for key in (
            "energy_sources",
            "device_consumption",
            "device_consumption_water",
        ):
            if key in update:
                data[key] = update[key]

        # Process energy sources and set stat_rate for power configs
        if "energy_sources" in update:
            data["energy_sources"] = self._process_energy_sources(
                data["energy_sources"]
            )

        self.data = data
        self._store.async_delay_save(lambda: data, 60)

        if not self._update_listeners:
            return

        await asyncio.gather(*(listener() for listener in self._update_listeners))

    def _process_energy_sources(self, sources: list[SourceType]) -> list[SourceType]:
        """Process energy sources and set stat_rate for power configs."""
        from .helpers import generate_power_sensor_entity_id  # noqa: PLC0415

        processed: list[SourceType] = []
        for source in sources:
            if source["type"] == "battery":
                source = self._process_battery_power(
                    source, generate_power_sensor_entity_id
                )
            elif source["type"] == "grid":
                source = self._process_grid_power(
                    source, generate_power_sensor_entity_id
                )
            processed.append(source)
        return processed

    def _process_battery_power(
        self,
        source: BatterySourceType,
        generate_entity_id: Callable[[str, PowerConfig], str],
    ) -> BatterySourceType:
        """Set stat_rate for battery if power_config is specified."""
        if "power_config" not in source:
            return source

        config = source["power_config"]

        # If power_config has stat_rate (standard), just use it directly
        if "stat_rate" in config:
            return {**source, "stat_rate": config["stat_rate"]}

        # For inverted or two-sensor config, set stat_rate to the generated entity_id
        return {**source, "stat_rate": generate_entity_id("battery", config)}

    def _process_grid_power(
        self,
        source: GridSourceType,
        generate_entity_id: Callable[[str, PowerConfig], str],
    ) -> GridSourceType:
        """Set stat_rate for grid if power_config is specified."""
        if "power_config" not in source:
            return source

        config = source["power_config"]

        # If power_config has stat_rate (standard), just use it directly
        if "stat_rate" in config:
            return {**source, "stat_rate": config["stat_rate"]}

        # For inverted or two-sensor config, set stat_rate to the generated entity_id
        return {**source, "stat_rate": generate_entity_id("grid", config)}

    @callback
    def async_listen_updates(self, update_listener: Callable[[], Awaitable]) -> None:
        """Listen for data updates."""
        self._update_listeners.append(update_listener)
