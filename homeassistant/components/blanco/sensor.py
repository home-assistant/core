"""Sensor platform for the BLANCO integration."""

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
    StateType,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BlancoConfigEntry
from .const import DOMAIN
from .coordinator import BlancoDataUpdateCoordinator
from .definitions import BLANCO_DEVICE_NAMES, BlancoDeviceType

# Updates are driven by the DataUpdateCoordinator; no concurrency limit needed.
PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class BlancoSensorEntityDescription(SensorEntityDescription):
    """Describes a BLANCO sensor entity."""

    # Receives the full coordinator.data dict and returns the sensor value.
    value_fn: Callable[[dict[str, Any]], StateType | datetime] | None = field(
        default=None, compare=False
    )


# ── Common sensors (all device types) ────────────────────────────────────────

_DESC_ONLINE = BlancoSensorEntityDescription(
    key="online",
    translation_key="online",
    value_fn=lambda data: (
        datetime.fromtimestamp(ts / 1000, tz=UTC)
        if (ts := data.get("system", {}).get("info", {}).get("online")) is not None
        else None
    ),
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)

_DESC_ERROR_COUNT = BlancoSensorEntityDescription(
    key="error_count",
    translation_key="error_count",
    value_fn=lambda data: sum(
        1
        for e in data.get("errors", {}).get("errors", [])
        if e.get("err_type") in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
    ),
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    entity_category=EntityCategory.DIAGNOSTIC,
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
    value_fn=lambda data: (
        data.get("settings", {}).get("params", {}).get("set_point_cooling")
    ),
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # range: 4–10 °C
    suggested_display_precision=0,
)
_DESC_SET_POINT_HEATING = BlancoSensorEntityDescription(
    key="set_point_heating",
    translation_key="set_point_heating",
    value_fn=lambda data: (
        data.get("settings", {}).get("params", {}).get("set_point_heating")
    ),
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # range: 65–100 °C
    suggested_display_precision=0,
)
_DESC_CO2_REST = BlancoSensorEntityDescription(
    key="co2_rest",
    translation_key="co2_rest",
    value_fn=lambda data: data.get("status", {}).get("params", {}).get("co2_rest"),
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,  # range: 0–100 %
    suggested_display_precision=0,
)
_DESC_FILTER_REST = BlancoSensorEntityDescription(
    key="filter_rest",
    translation_key="filter_rest",
    value_fn=lambda data: data.get("status", {}).get("params", {}).get("filter_rest"),
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

# ── Lookup: device type → descriptions (common + device-specific) ─────────────

SENSOR_DESCRIPTIONS_BY_TYPE: dict[
    BlancoDeviceType, tuple[BlancoSensorEntityDescription, ...]
] = {  # Maps each device type to its full set of sensor descriptions.
    BlancoDeviceType.AIO: SENSOR_DESCRIPTIONS_COMMON + SENSOR_DESCRIPTIONS_AIO,
    BlancoDeviceType.SODA: SENSOR_DESCRIPTIONS_COMMON + SENSOR_DESCRIPTIONS_SODA,
    BlancoDeviceType.SODA2: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.FILTER: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.HOT: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.SELECT: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.FLEXON: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.SEPURA: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.AQUA: SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.BIOSORT: SENSOR_DESCRIPTIONS_COMMON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO sensors from a config entry."""
    coordinator = entry.runtime_data
    dev_type = coordinator.dev_type
    descriptions = (
        SENSOR_DESCRIPTIONS_BY_TYPE.get(dev_type, SENSOR_DESCRIPTIONS_COMMON)
        if dev_type is not None
        else SENSOR_DESCRIPTIONS_COMMON
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
        system_params: dict[str, Any] = coordinator.data.get("system", {}).get(
            "params", {}
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.dev_id)},
            name=system_params.get("dev_name", "BLANCO"),
            manufacturer="BLANCO",
            model=(
                BLANCO_DEVICE_NAMES.get(coordinator.dev_type)
                if coordinator.dev_type is not None
                else None
            ),
            serial_number=coordinator.serial,
            sw_version=system_params.get("sw_ver_main_con"),
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
    def native_value(self) -> StateType | datetime:
        """Return the current sensor value."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
