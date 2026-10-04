"""Sensor platform for the BLANCO integration."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, override

from blanco_smart_home_api_client import BLANCO_DEVICE_NAMES, BlancoErrorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BlancoConfigEntry
from .const import DOMAIN
from .coordinator import BlancoDataUpdateCoordinator

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

_DESC_ERROR_COUNT_CRITICAL = BlancoSensorEntityDescription(
    key="error_count_critical",
    translation_key="error_count_critical",
    value_fn=lambda data: sum(
        1
        for e in data.get("errors", {}).get("errors", [])
        if e.get("err_type") == BlancoErrorType.CRITICAL
    ),
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    entity_category=EntityCategory.DIAGNOSTIC,
)

_DESC_ERROR_COUNT_WARNING = BlancoSensorEntityDescription(
    key="error_count_warning",
    translation_key="error_count_warning",
    value_fn=lambda data: sum(
        1
        for e in data.get("errors", {}).get("errors", [])
        if e.get("err_type") == BlancoErrorType.WARNING
    ),
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    entity_category=EntityCategory.DIAGNOSTIC,
)

SENSOR_DESCRIPTIONS_COMMON: tuple[BlancoSensorEntityDescription, ...] = (
    _DESC_ONLINE,
    _DESC_ERROR_COUNT_CRITICAL,
    _DESC_ERROR_COUNT_WARNING,
)
"""Sensor descriptions shared by every BLANCO device type.

Currently the only sensors provided — the coordinator only polls /system and
/errors; device-specific temperature, CO2, and filter sensors require the
/status and /settings endpoints, which are not polled yet.
"""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlancoSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS_COMMON
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
        # device_info is implemented as a property below so that sw_version
        # (and dev_name) stay current across coordinator updates.

    @override
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info built from the latest coordinator data."""
        system_params: dict[str, Any] = self.coordinator.data.get("system", {}).get(
            "params", {}
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.dev_id)},
            name=system_params.get("dev_name", "BLANCO"),
            manufacturer="BLANCO",
            model=(
                BLANCO_DEVICE_NAMES.get(self.coordinator.dev_type)
                if self.coordinator.dev_type is not None
                else None
            ),
            serial_number=self.coordinator.serial,
            sw_version=system_params.get("sw_ver_main_con"),
        )

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return filtered error list for the critical/warning error-count sensors."""
        key = self.entity_description.key
        if key == "error_count_critical":
            severity = BlancoErrorType.CRITICAL
        elif key == "error_count_warning":
            severity = BlancoErrorType.WARNING
        else:
            return None
        all_errors: list[dict[str, Any]] = self.coordinator.data.get("errors", {}).get(
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
                for entry in all_errors
                if entry.get("err_type") == severity
            ]
        }

    @override
    @property
    def native_value(self) -> StateType | datetime:
        """Return the current sensor value."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
