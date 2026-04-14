"""Binary sensor platform for the BLANCO integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from blanco_smart_home_api_client import BlancoErrorType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
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
class BlancoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a BLANCO binary sensor entity."""

    # Top-level key in coordinator.data (e.g. "system", "settings")
    # Leave empty ("") to use the custom has_error logic instead.
    data_key: str = ""
    # Sub-section within data[data_key]: "params" or "info"
    source: str = "params"
    # Field name inside data[data_key][source]
    param_key: str = ""
    # When True the raw boolean value is negated before returning
    invert: bool = False


# ── Common binary sensors (all device types) ──────────────────────────────────

_DESC_CONNECTED = BlancoBinarySensorEntityDescription(
    key="connected",
    translation_key="connected",
    data_key="system",
    source="info",
    param_key="connected",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)

_DESC_HAS_ERROR = BlancoBinarySensorEntityDescription(
    key="has_error",
    translation_key="has_error",
    device_class=BinarySensorDeviceClass.PROBLEM,
)

BINARY_SENSOR_DESCRIPTIONS_COMMON: tuple[BlancoBinarySensorEntityDescription, ...] = (
    _DESC_CONNECTED,
    _DESC_HAS_ERROR,
)
"""Binary sensor descriptions shared by every BLANCO device type."""

# ── AIO (CHOICE.ALL) ──────────────────────────────────────────────────────────

_DESC_CHILD_PROTECT = BlancoBinarySensorEntityDescription(
    key="child_protect",
    translation_key="child_protect",
    data_key="settings",
    source="params",
    param_key="child_protect",
    invert=True,  # child_protect=False means hot-water mode is active (True)
)

_DESC_ABSENCE_MODE_ACTIVE = BlancoBinarySensorEntityDescription(
    key="absence_mode_active",
    translation_key="absence_mode_active",
    data_key="settings",
    source="params",
    param_key="absence_mode_active",
)

BINARY_SENSOR_DESCRIPTIONS_AIO: tuple[BlancoBinarySensorEntityDescription, ...] = (
    _DESC_CHILD_PROTECT,
    _DESC_ABSENCE_MODE_ACTIVE,
)
"""Binary sensor descriptions specific to the AIO (CHOICE.ALL) device type."""

# ── Lookup: device type → descriptions (common + device-specific) ─────────────

BINARY_SENSOR_DESCRIPTIONS_BY_TYPE: dict[
    BlancoDeviceType, tuple[BlancoBinarySensorEntityDescription, ...]
] = {  # Maps each device type to its full set of binary sensor descriptions.
    BlancoDeviceType.AIO: BINARY_SENSOR_DESCRIPTIONS_COMMON
    + BINARY_SENSOR_DESCRIPTIONS_AIO,
    BlancoDeviceType.SODA: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.SODA2: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.FILTER: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.HOT: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.SELECT: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.FLEXON: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.SEPURA: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.AQUA: BINARY_SENSOR_DESCRIPTIONS_COMMON,
    BlancoDeviceType.BIOSORT: BINARY_SENSOR_DESCRIPTIONS_COMMON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO binary sensors from a config entry."""
    coordinator = entry.runtime_data
    descriptions = BINARY_SENSOR_DESCRIPTIONS_BY_TYPE.get(
        coordinator.dev_type, BINARY_SENSOR_DESCRIPTIONS_COMMON
    )
    async_add_entities(
        BlancoBinarySensorEntity(coordinator, description)
        for description in descriptions
    )


class BlancoBinarySensorEntity(
    CoordinatorEntity[BlancoDataUpdateCoordinator], BinarySensorEntity
):
    """A binary sensor entity for a BLANCO device."""

    entity_description: BlancoBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlancoDataUpdateCoordinator,
        description: BlancoBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.dev_id}_{description.key}"
        # Force English entity_id regardless of the HA UI language setting.
        # Without this, HA derives the entity_id from the translated name at
        # first registration, producing locale-specific IDs (e.g. "verbunden").
        self.entity_id = (
            f"binary_sensor.blanco_{slugify(coordinator.serial)}_{description.key}"
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
    def is_on(self) -> bool | None:
        """Return the binary state of the sensor."""
        if self.entity_description.data_key:
            # Generic path: read from data[data_key][source][param_key]
            section: dict[str, Any] = self.coordinator.data.get(
                self.entity_description.data_key, {}
            )
            value = section.get(self.entity_description.source, {}).get(
                self.entity_description.param_key
            )
            if value is None:
                return None
            result = bool(value)
            return (not result) if self.entity_description.invert else result

        # Special case: has_error — iterate over the errors list
        errors: list[dict[str, Any]] = self.coordinator.data.get("errors", {}).get(
            "errors", []
        )
        return any(
            entry["err_type"] in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
            for entry in errors
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the error list as attributes (only for the has_error sensor)."""
        if self.entity_description.key != "has_error":
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
