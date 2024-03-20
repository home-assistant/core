"""Support for Xiaomi event entities."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import format_discovered_event_class, format_event_dispatcher_name
from .const import (
    DOMAIN,
    EVENT_CLASS_BUTTON,
    EVENT_CLASS_CUBE,
    EVENT_CLASS_DIMMER,
    EVENT_CLASS_ERROR,
    EVENT_CLASS_FINGERPRINT,
    EVENT_CLASS_LOCK,
    EVENT_CLASS_MOTION,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    XiaomiBleEvent,
)
from .coordinator import XiaomiActiveBluetoothProcessorCoordinator

DESCRIPTIONS_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: EventEntityDescription(
        key=EVENT_CLASS_BUTTON,
        translation_key="button",
        event_types=[
            "press",
            "double_press",
            "long_press",
        ],
        device_class=EventDeviceClass.BUTTON,
    ),
    EVENT_CLASS_CUBE: EventEntityDescription(
        key=EVENT_CLASS_CUBE,
        translation_key="cube",
        event_types=[
            "rotate_left",
            "rotate_right",
        ],
    ),
    EVENT_CLASS_DIMMER: EventEntityDescription(
        key=EVENT_CLASS_DIMMER,
        translation_key="dimmer",
        event_types=[
            "press",
            "long_press",
            "rotate_left",
            "rotate_right",
            "rotate_left_pressed",
            "rotate_right_pressed",
        ],
    ),
    EVENT_CLASS_ERROR: EventEntityDescription(
        key=EVENT_CLASS_ERROR,
        translation_key="error",
        event_types=[
            "frequent_unlocking_with_incorrect_password",
            "frequent_unlocking_with_wrong_fingerprints",
            "operation_timeout_password_input_timeout",
            "lock_picking",
            "reset_button_is_pressed",
            "the_wrong_key_is_frequently_unlocked",
            "foreign_body_in_the_keyhole",
            "the_key_has_not_been_taken_out",
            "error_nfc_frequently_unlocks",
            "timeout_is_not_locked_as_required",
            "failure_to_unlock_frequently_in_multiple_ways",
            "unlocking_the_face_frequently_fails",
            "failure_to_unlock_the_vein_frequently",
            "hijacking_alarm",
            "unlock_inside_the_door_after_arming",
            "palmprints_frequently_fail_to_unlock",
            "the_safe_was_moved",
            "the_battery_level_is_less_than_10_percent",
            "the_battery_is_less_than_5_percent",
            "the_fingerprint_sensor_is_abnormal",
            "the_accessory_battery_is_low",
            "mechanical_failure",
            "the_lock_sensor_is_faulty",
        ],
    ),
    EVENT_CLASS_FINGERPRINT: EventEntityDescription(
        key=EVENT_CLASS_FINGERPRINT,
        translation_key="fingerprint",
        event_types=[
            "match_successful",
            "match_failed",
            "low_quality_too_light_fuzzy",
            "insufficient_area",
            "skin_is_too_dry",
            "skin_is_too_wet",
        ],
    ),
    EVENT_CLASS_LOCK: EventEntityDescription(
        key=EVENT_CLASS_LOCK,
        translation_key="lock",
        event_types=[
            "lock_outside_the_door",
            "unlock_outside_the_door",
            "lock_inside_the_door",
            "unlock_inside_the_door",
            "locked",
            "turn_on_antilock",
            "release_the_antilock",
            "turn_on_child_lock",
            "turn_off_child_lock",
            "abnormal",
        ],
    ),
    EVENT_CLASS_MOTION: EventEntityDescription(
        key=EVENT_CLASS_MOTION,
        translation_key="motion",
        event_types=["motion_detected"],
        device_class=EventDeviceClass.MOTION,
    ),
}


class XiaomiEventEntity(EventEntity):
    """Representation of a Xiaomi event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        address: str,
        event_class: str,
        event: XiaomiBleEvent | None,
    ) -> None:
        """Initialise a Xiaomi event entity."""
        self._update_signal = format_event_dispatcher_name(address, event_class)
        # event_class is something like "button" or "motion"
        # and it maybe postfixed with "_1", "_2", "_3", etc
        # If there is only one button then it will be "button"
        base_event_class, _, postfix = event_class.partition("_")
        base_description = DESCRIPTIONS_BY_EVENT_CLASS[base_event_class]
        self.entity_description = replace(base_description, key=event_class)
        postfix_name = f" {postfix}" if postfix else ""
        self._attr_name = f"{base_event_class.title()}{postfix_name}"
        # Matches logic in PassiveBluetoothProcessorEntity
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )
        self._attr_unique_id = f"{address}-{event_class}"
        # If the event is provided then we can set the initial state
        # since the event itself is likely what triggered the creation
        # of this entity. We have to do this at creation time since
        # entities are created dynamically and would otherwise miss
        # the initial state.
        if event:
            self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._update_signal,
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: XiaomiBleEvent) -> None:
        self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xiaomi event."""
    coordinator: XiaomiActiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    address = coordinator.address
    ent_reg = er.async_get(hass)
    async_add_entities(
        # Matches logic in PassiveBluetoothProcessorEntity
        XiaomiEventEntity(address_event_class[0], address_event_class[2], None)
        for ent_reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if ent_reg_entry.domain == "event"
        and (address_event_class := ent_reg_entry.unique_id.partition("-"))
    )

    @callback
    def _async_discovered_event_class(event_class: str, event: XiaomiBleEvent) -> None:
        """Handle a newly discovered event class with or without a postfix."""
        async_add_entities([XiaomiEventEntity(address, event_class, event)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_discovered_event_class(address),
            _async_discovered_event_class,
        )
    )
