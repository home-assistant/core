"""Support for Samsung Printers with SyncThru web interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pysyncthru import SyncThru, SyncthruState

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SyncThruConfigEntry
from .entity import SyncthruEntity

SYNCTHRU_STATE_HUMAN = {
    SyncthruState.INVALID: "invalid",
    SyncthruState.OFFLINE: "unreachable",
    SyncthruState.NORMAL: "normal",
    SyncthruState.UNKNOWN: "unknown",
    SyncthruState.WARNING: "warning",
    SyncthruState.TESTING: "testing",
    SyncthruState.ERROR: "error",
}


@dataclass(frozen=True, kw_only=True)
class SyncThruSensorDescription(SensorEntityDescription):
    """Describes a SyncThru sensor entity."""

    value_fn: Callable[[SyncThru], str | None]
    extra_state_attributes_fn: Callable[[SyncThru], dict[str, str | int]] | None = None


def get_toner_entity_description(color: str) -> SyncThruSensorDescription:
    """Get toner entity description for a specific color."""
    return SyncThruSensorDescription(
        key=f"toner_{color}",
        translation_key=f"toner_{color}",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda printer: printer.toner_status().get(color, {}).get("remaining"),
        extra_state_attributes_fn=lambda printer: printer.toner_status().get(color, {}),
    )


def get_drum_entity_description(color: str) -> SyncThruSensorDescription:
    """Get drum entity description for a specific color."""
    return SyncThruSensorDescription(
        key=f"drum_{color}",
        translation_key=f"drum_{color}",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda printer: printer.drum_status().get(color, {}).get("remaining"),
        extra_state_attributes_fn=lambda printer: printer.drum_status().get(color, {}),
    )


def get_input_tray_entity_description(tray: str) -> SyncThruSensorDescription:
    """Get input tray entity description for a specific tray."""
    placeholders = {}
    translation_key = f"tray_{tray}"
    if "_" in tray:
        _, identifier = tray.split("_")
        placeholders["tray_number"] = identifier
        translation_key = "tray"
    return SyncThruSensorDescription(
        key=f"tray_{tray}",
        translation_key=translation_key,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_placeholders=placeholders,
        value_fn=(
            lambda printer: printer.input_tray_status().get(tray, {}).get("newError")
            or "Ready"
        ),
        extra_state_attributes_fn=(
            lambda printer: printer.input_tray_status().get(tray, {})
        ),
    )


def get_output_tray_entity_description(tray: int) -> SyncThruSensorDescription:
    """Get output tray entity description for a specific tray."""
    return SyncThruSensorDescription(
        key=f"output_tray_{tray}",
        translation_key="output_tray",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_placeholders={"tray_number": str(tray)},
        value_fn=(
            lambda printer: printer.output_tray_status().get(tray, {}).get("status")
            or "Ready"
        ),
        extra_state_attributes_fn=(
            lambda printer: cast(
                dict[str, str | int], printer.output_tray_status().get(tray, {})
            )
        ),
    )


SENSOR_TYPES: tuple[SyncThruSensorDescription, ...] = (
    SyncThruSensorDescription(
        key="active_alerts",
        translation_key="active_alerts",
        value_fn=lambda printer: printer.raw().get("GXI_ACTIVE_ALERT_TOTAL"),
    ),
    SyncThruSensorDescription(
        key="main",
        name=None,
        value_fn=lambda printer: SYNCTHRU_STATE_HUMAN[printer.device_status()],
        extra_state_attributes_fn=lambda printer: {
            "display_text": printer.device_status_details(),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SyncThruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up from config entry."""

    coordinator = config_entry.runtime_data
    printer = coordinator.data

    supp_toner = printer.toner_status(filter_supported=True)
    supp_drum = printer.drum_status(filter_supported=True)
    supp_tray = printer.input_tray_status(filter_supported=True)
    supp_output_tray = printer.output_tray_status()

    entities: list[SyncThruSensorDescription] = [
        get_toner_entity_description(color) for color in supp_toner
    ]
    entities.extend(get_drum_entity_description(color) for color in supp_drum)
    entities.extend(get_input_tray_entity_description(key) for key in supp_tray)
    entities.extend(get_output_tray_entity_description(key) for key in supp_output_tray)

    async_add_entities(
        SyncThruSensor(coordinator, description)
        for description in SENSOR_TYPES + tuple(entities)
    )


class SyncThruSensor(SyncthruEntity, SensorEntity):
    """Implementation of an abstract Samsung Printer sensor platform."""

    _attr_icon = "mdi:printer"
    entity_description: SyncThruSensorDescription

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.coordinator.data
            )
        return None
