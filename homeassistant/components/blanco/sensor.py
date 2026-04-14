"""Sensor platform for the BLANCO integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from blanco_smart_home_api_client import BlancoErrorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import BlancoConfigEntry
from .const import DOMAIN
from .coordinator import BlancoDataUpdateCoordinator
from .definitions import BLANCO_DEVICE_NAMES, BlancoDeviceType

# Updates are driven by the DataUpdateCoordinator; no concurrency limit needed.
PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class BlancoSensorEntityDescription(SensorEntityDescription):
    """Describes a BLANCO sensor entity."""

    # Top-level key in coordinator.data (e.g. "settings", "status", "system")
    data_key: str = ""
    # Sub-section within data[data_key]: "params" or "info"
    source: str = "params"
    # Field name inside data[data_key][source] — used when value_fn is None
    param_key: str = ""
    # Optional computed value function — receives data[data_key][source] (dict or
    # list depending on the source key) and returns the sensor value.
    # Takes priority over param_key when set.
    value_fn: Callable[[Any], Any] | None = field(default=None, compare=False)


# ── AQUA computed helpers ─────────────────────────────────────────────────────


def _aqua_filter_remaining_volume(params: dict[str, Any]) -> float | None:
    """Filter remaining volume in litres: max(0, 2000 - filter_flow_total / 1000)."""
    flow = params.get("filter_flow_total")
    if flow is None:
        return None
    return round(max(0.0, 2000.0 - flow / 1000.0), 1)


def _aqua_filter_remaining_days(params: dict[str, Any]) -> float | None:
    """Filter remaining runtime in days: max(0, 120 - filter_age / 24)."""
    age = params.get("filter_age")
    if age is None:
        return None
    return round(max(0.0, 120.0 - age / 24.0), 1)


def _aqua_filter_rest(params: dict[str, Any]) -> float | None:
    """Filter remaining capacity in %: min(vol/2000, days/120) * 100."""
    vol = _aqua_filter_remaining_volume(params)
    days = _aqua_filter_remaining_days(params)
    if vol is None or days is None:
        return None
    return round(min(vol / 2000.0, days / 120.0) * 100.0, 1)


# ── Common sensors (all device types) ────────────────────────────────────────

_DESC_ONLINE = BlancoSensorEntityDescription(
    key="online",
    translation_key="online",
    data_key="system",
    source="info",
    param_key="online",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)

_DESC_ERROR_COUNT = BlancoSensorEntityDescription(
    key="error_count",
    translation_key="error_count",
    data_key="errors",
    source="errors",
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda data: sum(
        1
        for e in (data if isinstance(data, list) else [])
        if e.get("err_type") in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
    ),
)

SENSOR_DESCRIPTIONS_COMMON: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_ONLINE,
    _DESC_ERROR_COUNT,
)
"""Sensor descriptions shared by every BLANCO device type."""

# ── AIO (CHOICE.ALL) — full set ───────────────────────────────────────────────

_DESC_SET_POINT_COOLING = BlancoSensorEntityDescription(
    key="set_point_cooling",
    translation_key="set_point_cooling",
    data_key="settings",
    param_key="set_point_cooling",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # range: 4–10 °C
    suggested_display_precision=0,
)
_DESC_SET_POINT_HEATING = BlancoSensorEntityDescription(
    key="set_point_heating",
    translation_key="set_point_heating",
    data_key="settings",
    param_key="set_point_heating",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # range: 65–100 °C
    suggested_display_precision=0,
)
_DESC_CO2_REST = BlancoSensorEntityDescription(
    key="co2_rest",
    translation_key="co2_rest",
    data_key="status",
    param_key="co2_rest",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,  # range: 0–100 %
    suggested_display_precision=0,
)
_DESC_FILTER_REST = BlancoSensorEntityDescription(
    key="filter_rest",
    translation_key="filter_rest",
    data_key="status",
    param_key="filter_rest",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,  # range: 0–100 %
    suggested_display_precision=0,
)

SENSOR_DESCRIPTIONS_AIO: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_SET_POINT_COOLING,
    _DESC_SET_POINT_HEATING,
    _DESC_CO2_REST,
    _DESC_FILTER_REST,
)
"""Sensor descriptions specific to the AIO (CHOICE.ALL) device type."""

# ── SODA (EVOL-S PRO) — no hot water temperature ─────────────────────────────

SENSOR_DESCRIPTIONS_SODA: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_SET_POINT_COOLING,
    _DESC_CO2_REST,
    _DESC_FILTER_REST,
)
"""Sensor descriptions specific to the SODA (EVOL-S PRO) device type."""

# ── AQUA — computed filter sensors ───────────────────────────────────────────

_DESC_AQUA_FILTER_REMAINING_VOLUME = BlancoSensorEntityDescription(
    key="filter_remaining_volume",
    translation_key="filter_remaining_volume",
    data_key="status",
    source="params",
    value_fn=_aqua_filter_remaining_volume,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_AQUA_FILTER_REMAINING_DAYS = BlancoSensorEntityDescription(
    key="filter_remaining_days",
    translation_key="filter_remaining_days",
    data_key="status",
    source="params",
    value_fn=_aqua_filter_remaining_days,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTime.DAYS,
    suggested_display_precision=0,
)
_DESC_AQUA_FILTER_REST = BlancoSensorEntityDescription(
    key="filter_rest",
    translation_key="filter_rest",
    data_key="status",
    source="params",
    value_fn=_aqua_filter_rest,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=0,
)

SENSOR_DESCRIPTIONS_AQUA: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_AQUA_FILTER_REMAINING_VOLUME,
    _DESC_AQUA_FILTER_REMAINING_DAYS,
    _DESC_AQUA_FILTER_REST,
)
"""Sensor descriptions specific to the AQUA device type (computed filter sensors)."""

# ── Actions — water consumption sensors ───────────────────────────────────────

_DESC_LAST_DISPENSING = BlancoSensorEntityDescription(
    key="last_dispensing",
    translation_key="last_dispensing",
    data_key="actions",
    source="totals",
    param_key="last",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfVolume.MILLILITERS,
    suggested_display_precision=0,
)
_DESC_WATER_TOTAL = BlancoSensorEntityDescription(
    key="water_total",
    translation_key="water_total",
    data_key="actions",
    source="totals",
    param_key="all",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_STILL = BlancoSensorEntityDescription(
    key="water_still",
    translation_key="water_still",
    data_key="actions",
    source="totals",
    param_key="still",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_MEDIUM = BlancoSensorEntityDescription(
    key="water_medium",
    translation_key="water_medium",
    data_key="actions",
    source="totals",
    param_key="medium",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_CLASSIC = BlancoSensorEntityDescription(
    key="water_classic",
    translation_key="water_classic",
    data_key="actions",
    source="totals",
    param_key="classic",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_HOT = BlancoSensorEntityDescription(
    key="water_hot",
    translation_key="water_hot",
    data_key="actions",
    source="totals",
    param_key="hot",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)

SENSOR_DESCRIPTIONS_ACTIONS_BASE: tuple[BlancoSensorEntityDescription, ...] = ()
"""Water consumption sensor descriptions for device types without specific action support."""

SENSOR_DESCRIPTIONS_ACTIONS_SODA: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_LAST_DISPENSING,
    _DESC_WATER_TOTAL,
    _DESC_WATER_STILL,
    _DESC_WATER_MEDIUM,
    _DESC_WATER_CLASSIC,
)
"""Water consumption sensor descriptions for SODA devices (STILL, MEDIUM, CLASSIC)."""

SENSOR_DESCRIPTIONS_ACTIONS_AQUA: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_LAST_DISPENSING,
    _DESC_WATER_TOTAL,
)
"""Water consumption sensor descriptions for AQUA devices (last dispensing and total only)."""

SENSOR_DESCRIPTIONS_ACTIONS_AIO: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_LAST_DISPENSING,
    _DESC_WATER_TOTAL,
    _DESC_WATER_STILL,
    _DESC_WATER_MEDIUM,
    _DESC_WATER_CLASSIC,
    _DESC_WATER_HOT,
)
"""Water consumption sensor descriptions for the AIO device type (adds HOT water)."""

# ── Stats — time-range water consumption sensors ──────────────────────────────

_DESC_WATER_TODAY = BlancoSensorEntityDescription(
    key="water_today",
    translation_key="water_today",
    data_key="stats",
    source="totals",
    param_key="today",
    device_class=SensorDeviceClass.WATER,
    # TOTAL (not TOTAL_INCREASING) because the value resets at each period
    # boundary (e.g. midnight for "today") and can therefore decrease.
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_WEEK = BlancoSensorEntityDescription(
    key="water_week",
    translation_key="water_week",
    data_key="stats",
    source="totals",
    param_key="week",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_MONTH = BlancoSensorEntityDescription(
    key="water_month",
    translation_key="water_month",
    data_key="stats",
    source="totals",
    param_key="month",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)
_DESC_WATER_YEAR = BlancoSensorEntityDescription(
    key="water_year",
    translation_key="water_year",
    data_key="stats",
    source="totals",
    param_key="year",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
)

SENSOR_DESCRIPTIONS_STATS_WATER: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_WATER_TODAY,
    _DESC_WATER_WEEK,
    _DESC_WATER_MONTH,
    _DESC_WATER_YEAR,
)
"""Time-range water consumption sensors sourced from the /stats endpoint (AIO, SODA, AQUA)."""

# ── Lookup: device type → descriptions (common + device-specific) ─────────────

SENSOR_DESCRIPTIONS_BY_TYPE: dict[
    BlancoDeviceType, tuple[BlancoSensorEntityDescription, ...]
] = {  # Maps each device type to its full set of sensor descriptions.
    BlancoDeviceType.AIO: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_AIO
    + SENSOR_DESCRIPTIONS_ACTIONS_AIO
    + SENSOR_DESCRIPTIONS_STATS_WATER,
    BlancoDeviceType.SODA: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_SODA
    + SENSOR_DESCRIPTIONS_ACTIONS_SODA
    + SENSOR_DESCRIPTIONS_STATS_WATER,
    BlancoDeviceType.SODA2: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.FILTER: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.HOT: SENSOR_DESCRIPTIONS_COMMON + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.SELECT: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.FLEXON: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.SEPURA: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
    BlancoDeviceType.AQUA: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_AQUA
    + SENSOR_DESCRIPTIONS_ACTIONS_AQUA
    + SENSOR_DESCRIPTIONS_STATS_WATER,
    BlancoDeviceType.BIOSORT: SENSOR_DESCRIPTIONS_COMMON
    + SENSOR_DESCRIPTIONS_ACTIONS_BASE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO sensors from a config entry."""
    coordinator = entry.runtime_data
    descriptions = SENSOR_DESCRIPTIONS_BY_TYPE.get(
        coordinator.dev_type, SENSOR_DESCRIPTIONS_COMMON
    )
    async_add_entities(
        BlancoSensorEntity(coordinator, description) for description in descriptions
    )


class BlancoSensorEntity(CoordinatorEntity[BlancoDataUpdateCoordinator], SensorEntity):
    """A sensor entity for a BLANCO device."""

    entity_description: BlancoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlancoDataUpdateCoordinator,
        description: BlancoSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.dev_id}_{description.key}"
        # Force English entity_id regardless of the HA UI language setting.
        # Without this, HA derives the entity_id from the translated name at
        # first registration, producing locale-specific IDs (e.g. "co2_restkapazitat").
        self.entity_id = (
            f"sensor.blanco_{slugify(coordinator.serial)}_{description.key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        system_params: dict[str, Any] = self.coordinator.data.get("system", {}).get(
            "params", {}
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.dev_id)},
            name=system_params.get("dev_name", "BLANCO"),
            manufacturer="BLANCO",
            model=BLANCO_DEVICE_NAMES.get(self.coordinator.dev_type, "UNKNOWN"),
            serial_number=self.coordinator.serial,
            hw_version=system_params.get("sw_ver_main_con"),
            sw_version=system_params.get("sw_ver_comm_con"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return error list as attributes (only for the error_count sensor)."""
        if self.entity_description.key != "error_count":
            return None
        errors: list[dict[str, Any]] = self.coordinator.data.get("errors", {}).get(
            "errors", []
        )
        return {
            "errors": [
                {
                    "err_code": entry.get("err_code"),
                    "err_type": entry["err_type"].name
                    if entry.get("err_type") is not None
                    else None,
                    "err_ts": datetime.fromtimestamp(
                        entry["err_ts"] / 1000, tz=UTC
                    ).isoformat()
                    if entry.get("err_ts") is not None
                    else None,
                }
                for entry in errors
            ]
        }

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        section: dict[str, Any] = self.coordinator.data.get(
            self.entity_description.data_key, {}
        )
        data: dict[str, Any] = section.get(self.entity_description.source, {})

        if self.entity_description.value_fn is not None:
            value = self.entity_description.value_fn(data)
        else:
            value = data.get(self.entity_description.param_key)

        if value is None:
            return None
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            # API delivers UNIX timestamp in milliseconds → convert to datetime
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        return value
