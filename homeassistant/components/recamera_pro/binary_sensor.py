"""Binary sensors for selected reCamera Pro detection rules."""

from recamera_protocol import DetectedClass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import DOMAIN, SOURCE_UNAVAILABLE
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity
from .source_state import DetectionState, source_is_available

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up user-selected visual class sensors."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    known_classes = set(coordinator.selected_class_keys)
    motion_added = coordinator.data.motion.installed
    entities: list[BinarySensorEntity] = [
        RecameraClassBinarySensor(coordinator, coordinator.data.class_catalog[identity])
        for identity in known_classes
        if identity in coordinator.data.class_catalog
    ]
    if motion_added:
        entities.append(RecameraMotionBinarySensor(coordinator))
    async_add_entities(entities)
    _hide_removed_binary_sensors(hass, coordinator)

    @callback
    def _add_selected_classes() -> None:
        nonlocal motion_added
        new_entities: list[BinarySensorEntity] = []
        selected = coordinator.selected_class_keys
        for identity in selected - known_classes:
            detected_class = coordinator.data.class_catalog.get(identity)
            if detected_class is None:
                continue
            known_classes.add(identity)
            new_entities.append(RecameraClassBinarySensor(coordinator, detected_class))
        if not motion_added and coordinator.data.motion.installed:
            motion_added = True
            new_entities.append(RecameraMotionBinarySensor(coordinator))
        if new_entities:
            async_add_entities(new_entities)
            _hide_removed_binary_sensors(hass, coordinator)

    config_entry.async_on_unload(coordinator.async_add_listener(_add_selected_classes))


class RecameraClassBinarySensor(RecameraEntity, BinarySensorEntity):
    """Expose one explicitly selected source-scoped class."""

    _attr_icon = "mdi:target"

    def __init__(
        self,
        coordinator: RecameraCoordinator,
        detected_class: DetectedClass,
    ) -> None:
        """Initialize a selected class sensor."""
        super().__init__(coordinator)
        self.detected_class = detected_class
        self._attr_translation_key = "visual_class"
        self._attr_translation_placeholders = {"class_name": detected_class.class_name}
        self._attr_unique_id = coordinator.class_entity_unique_id(detected_class)

    @property
    def _state(self) -> DetectionState:
        """Return the builtin YOLO state."""
        return self.coordinator.data.visual

    @property
    def available(self) -> bool:
        """Return whether the source is not explicitly unavailable."""
        return super().available and source_is_available(self._state)

    @property
    def is_on(self) -> bool:
        """Return whether the selected class is active."""
        return self.coordinator.class_is_active(self.detected_class)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return stable class identity and source health."""
        return {
            "source_id": "builtin",
            "class_name": self.detected_class.class_name,
            "class_id": self.detected_class.class_id,
            "class_key": self.detected_class.key,
            "source_status": self._state.health,
        }


class RecameraMotionBinarySensor(RecameraEntity, BinarySensorEntity):
    """Expose the current device-side motion state."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_translation_key = "motion_active"

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the motion state sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_motion_active"

    @property
    def available(self) -> bool:
        """Return whether the motion App state is confirmed."""
        motion = self.coordinator.data.motion
        return bool(
            super().available
            and motion.installed
            and motion.app_health != SOURCE_UNAVAILABLE
        )

    @property
    def is_on(self) -> bool | None:
        """Return the confirmed motion state."""
        motion = self.coordinator.data.motion
        if not motion.running:
            return None
        return motion.motion

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return bounded motion diagnostics."""
        motion = self.coordinator.data.motion
        return {
            "source_id": "motion-detect",
            "app_running": motion.running,
            "app_health": motion.app_health,
            "error": motion.error,
        }


def _hide_removed_binary_sensors(
    hass: HomeAssistant, coordinator: RecameraCoordinator
) -> None:
    """Hide old sound and removed detection entities."""
    registry = er.async_get(hass)
    kept_unique_ids = {
        f"{coordinator.device_id}_motion_active",
        *(
            coordinator.class_entity_unique_id(item)
            for item in coordinator.data.class_catalog.values()
            if item.key in coordinator.selected_class_keys
        ),
    }
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != coordinator.config_entry.entry_id
            or not str(entry.entity_id).startswith("binary_sensor.")
            or entry.hidden_by == RegistryEntryHider.USER
        ):
            continue
        desired_hidden = (
            None
            if entry.unique_id in kept_unique_ids
            else RegistryEntryHider.INTEGRATION
        )
        if entry.hidden_by != desired_hidden:
            registry.async_update_entity(
                entry.entity_id,
                hidden_by=desired_hidden,
            )
