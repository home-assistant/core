"""Code for Livisi Events."""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LIVISI_STATE_CHANGE,
    LOGGER,
    WMD_DEVICE_TYPE,
    WSC2_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button devices."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add events."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[EventEntity] = []
        for device in shc_devices:
            if device["id"] not in known_devices and device["type"] == WSC2_DEVICE_TYPE:
                livisi_event1: EventEntity = LivisiButtonEvent(
                    config_entry, coordinator, device, entity_suffix="top"
                )
                entities.append(livisi_event1)
                livisi_event2: EventEntity = LivisiButtonEvent(
                    config_entry, coordinator, device, entity_suffix="bottom"
                )
                entities.append(livisi_event2)
                LOGGER.debug("Include device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                known_devices.add(device["id"])
            if device["id"] not in known_devices and device["type"] == WMD_DEVICE_TYPE:
                livisi_event: EventEntity = LivisiMotionEvent(
                    config_entry, coordinator, device
                )
                entities.append(livisi_event)
                LOGGER.debug("Include device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                known_devices.add(device["id"])
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiEvent(LivisiEntity, EventEntity):
    """Represents the livisi Event base class."""

    _attr_has_entity_name = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        capability_name: str,
        entity_suffix: str | None = None,
    ) -> None:
        """Initialize the Livisi Event."""
        super().__init__(config_entry, coordinator, device, entity_suffix=entity_suffix)
        self._capability_id = self.capabilities[capability_name]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._capability_id}",
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: dict[str, Any] | None) -> None:
        """Handle the event."""
        raise NotImplementedError()


class LivisiButtonEvent(LivisiEvent, EventEntity):
    """Represents a wall mounted Switch."""

    _attr_has_entity_name = False
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["single_press"]

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        entity_suffix: str | None = None,
    ) -> None:
        """Initialize the Livisi Button Event."""
        super().__init__(
            config_entry,
            coordinator,
            device,
            capability_name="PushButtonSensor",
            entity_suffix=entity_suffix,
        )
        self.__trigger_index = 0 if entity_suffix == "top" else 1

    @callback
    def _async_handle_event(self, event: dict[str, Any] | None) -> None:
        """Handle the push button event."""
        if (
            event is not None
            and self.__trigger_index == event["lastPressedButtonIndex"]
        ):
            self._trigger_event("single_press", event)
            self.async_write_ha_state()


class LivisiMotionEvent(LivisiEvent, EventEntity):
    """Represents a motion sensor."""

    _attr_has_entity_name = False
    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = ["motion"]
    __motion_detection_count = 0

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi Motion Event."""
        super().__init__(
            config_entry, coordinator, device, capability_name="MotionDetectionSensor"
        )

    @callback
    def _async_handle_event(self, event: dict[str, Any] | None) -> None:
        """Handle the motion sensor event."""
        # Prevent multiple detection events
        if (
            event is not None
            and event["motionDetectedCount"] > self.__motion_detection_count
        ):
            self._trigger_event("motion", event)
            self.__motion_detection_count = event["motionDetectedCount"]
            self.async_write_ha_state()
