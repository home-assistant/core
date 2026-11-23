"""Diagnostic sensors for builtin reCamera Pro YOLO state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from recamera_protocol import ResultObservation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import DOMAIN
from .coordinator import RecameraCoordinator, RecameraRuntimeData
from .entity import RecameraEntity
from .source_state import DetectionState, family_is_available

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RecameraSensorDescription(SensorEntityDescription):
    """Description for one reCamera sensor."""

    source_id: str = "builtin"
    use_source_availability: bool = True
    value_fn: Callable[[RecameraRuntimeData], Any]


def _summary_observation(state: DetectionState) -> ResultObservation | None:
    """Return the debounced current summary."""
    return state.summary_observation or state.last_event or state.last_observation


def _summary_class_name(state: DetectionState) -> str | None:
    """Return the debounced current class."""
    observation = _summary_observation(state)
    return observation.class_name if observation else None


def _summary_confidence(state: DetectionState) -> float | None:
    """Return confidence for the same event shown by the class sensor."""
    observation = _summary_observation(state)
    return round(observation.confidence * 100, 2) if observation else None


VISUAL_SENSORS = (
    RecameraSensorDescription(
        key="last_detection",
        translation_key="last_detection",
        source_id="visual",
        icon="mdi:target",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _summary_class_name(data.visual),
    ),
    RecameraSensorDescription(
        key="confidence",
        translation_key="confidence",
        source_id="visual",
        icon="mdi:percent",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _summary_confidence(data.visual),
    ),
    RecameraSensorDescription(
        key="last_event",
        translation_key="last_event",
        source_id="visual",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_source_availability=False,
        value_fn=lambda data: (
            data.visual.last_event.timestamp if data.visual.last_event else None
        ),
    ),
    RecameraSensorDescription(
        key="visual_source_status",
        translation_key="visual_source_status",
        source_id="visual",
        icon="mdi:access-point-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_source_availability=False,
        value_fn=lambda data: data.visual.health,
    ),
    RecameraSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        source_id="device",
        icon="mdi:package-up",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        use_source_availability=False,
        value_fn=lambda data: data.info.firmware_version,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up builtin YOLO diagnostic sensors."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    entities: list[SensorEntity] = [
        RecameraSensor(coordinator, description) for description in VISUAL_SENSORS
    ]
    async_add_entities(entities)
    _hide_removed_sensors(hass, coordinator)


class RecameraSensor(RecameraEntity, SensorEntity):
    """Representation of one reCamera sensor."""

    entity_description: RecameraSensorDescription

    def __init__(
        self,
        coordinator: RecameraCoordinator,
        description: RecameraSensorDescription,
    ) -> None:
        """Initialize a reCamera sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._last_state_signature = self._state_signature()

    @property
    def _source_state(self) -> DetectionState:
        """Return builtin YOLO state."""
        return self.coordinator.data.visual

    @property
    def available(self) -> bool:
        """Return whether the relevant source is not unavailable."""
        if not self.entity_description.use_source_availability:
            return super().available
        return super().available and family_is_available(self._source_state)

    @property
    @override
    def native_value(self) -> Any:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return source health and timestamp trust information."""
        if self.entity_description.source_id == "device":
            return {"source_id": "device"}
        state = self._source_state
        event = state.last_event
        is_event_sensor = (
            self.entity_description.device_class == SensorDeviceClass.TIMESTAMP
        )
        observation = event if is_event_sensor else _summary_observation(state)
        attributes: dict[str, object] = {
            "source_id": self.entity_description.source_id,
            "source_status": state.health,
            "source_reason": state.reason,
            "clock_invalid": state.clock_invalid,
            "last_class_key": (observation.class_key if observation else None),
        }
        if is_event_sensor:
            attributes.update(
                {
                    "last_event_received": (
                        event.received_at.isoformat() if event else None
                    ),
                    "last_event_clock_valid": (event.clock_valid if event else None),
                }
            )
        return attributes

    def _state_signature(self) -> tuple[object, ...]:
        """Return only values that should create an HA state update."""
        return (
            self.available,
            self.native_value,
            self.extra_state_attributes,
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Skip duplicate writes caused by unrelated source activity."""
        signature = self._state_signature()
        if signature == self._last_state_signature:
            return
        self._last_state_signature = signature
        super()._handle_coordinator_update()


def _hide_removed_sensors(
    hass: HomeAssistant, coordinator: RecameraCoordinator
) -> None:
    """Hide old sound sensors and removed optional entities."""
    registry = er.async_get(hass)
    device_id = coordinator.device_id
    kept = {f"{device_id}_{description.key}" for description in VISUAL_SENSORS}
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != coordinator.config_entry.entry_id
            or not str(entry.entity_id).startswith("sensor.")
            or entry.unique_id in kept
            or entry.hidden_by == RegistryEntryHider.USER
        ):
            continue
        if entry.hidden_by != RegistryEntryHider.INTEGRATION:
            registry.async_update_entity(
                entry.entity_id,
                hidden_by=RegistryEntryHider.INTEGRATION,
            )
