"""Event platform for Meross Bluetooth (MS220 / MS700)."""

from __future__ import annotations

import logging

from meross_ble import (
    MS220_EVENT_BUTTON_DOUBLE,
    MS220_EVENT_BUTTON_SINGLE,
    MS220_EVENT_DOORBELL,
    MS700_BUTTON_COUNT,
    MerossModel,
    ms700_button_enabled,
    ms700_default_button_name,
    ms700_logical_button,
)

from homeassistant.components.event import (
    ATTR_MULTI_PRESS_COUNT,
    ButtonEventType,
    DoorbellEventType,
    EventDeviceClass,
    EventEntity,
    EventExtraStoredData,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MerossBLEDataUpdateCoordinator, MerossConfigEntry
from .entity import MerossBLEEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MerossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meross BLE event entities from a config entry."""
    coordinator = entry.runtime_data
    if coordinator.model == MerossModel.MS220:
        async_add_entities(
            [
                MerossBLEMS220ButtonEventEntity(coordinator),
                MerossBLEMS220DoorbellEventEntity(coordinator),
            ]
        )
        return
    if coordinator.model == MerossModel.MS700:
        added_buttons: set[int] = set()

        @callback
        def _sync_ms700_button_entities() -> None:
            screen_enable = coordinator.device.data.get("screen_enable")
            if screen_enable is None:
                screen_enable = 0x01
            registry = er.async_get(hass)
            domain = entry.domain
            to_add: list[MerossBLEMS700ButtonEventEntity] = []
            for button_number in range(1, MS700_BUTTON_COUNT + 1):
                unique_id = f"{coordinator.base_unique_id}-button-{button_number}"
                entity_id = registry.async_get_entity_id(
                    Platform.EVENT, domain, unique_id
                )
                label = _ms700_button_label(coordinator, button_number)
                want = ms700_button_enabled(button_number, screen_enable)
                if want:
                    if button_number not in added_buttons:
                        to_add.append(
                            MerossBLEMS700ButtonEventEntity(
                                coordinator, button_number, label
                            )
                        )
                        added_buttons.add(button_number)
                    if entity_id is not None:
                        registry.async_update_entity(
                            entity_id,
                            disabled_by=None,
                            name=label,
                        )
                elif entity_id is not None:
                    registry.async_remove(entity_id)
                    added_buttons.discard(button_number)
            if to_add:
                async_add_entities(to_add)

        entry.async_on_unload(
            coordinator.async_add_listener(_sync_ms700_button_entities)
        )
        _sync_ms700_button_entities()


def _ms700_button_label(
    coordinator: MerossBLEDataUpdateCoordinator, button_number: int
) -> str:
    """Prefer a device/app custom name when present; else screenN-buttonM."""
    names = coordinator.device.data.get("button_names")
    if isinstance(names, dict):
        custom = names.get(button_number) or names.get(str(button_number))
        if isinstance(custom, str) and custom.strip():
            return custom.strip()
    return ms700_default_button_name(button_number)


class _MerossBLEEventEntity(MerossBLEEntity, EventEntity):
    """Event entity that does not restore last press across restarts."""

    async def async_get_last_event_data(self) -> EventExtraStoredData | None:
        return None


class MerossBLEMS220ButtonEventEntity(_MerossBLEEventEntity):
    """Physical button: single → press_end, double → multi_press_end."""

    _attr_translation_key = "button"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [
        ButtonEventType.PRESS_END,
        ButtonEventType.MULTI_PRESS_END,
    ]

    def __init__(self, coordinator: MerossBLEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}-button"

    @callback
    def _handle_coordinator_update(self) -> None:
        for _req_id, event_code in self.coordinator.last_new_events:
            if event_code == MS220_EVENT_BUTTON_SINGLE:
                self._trigger_event(ButtonEventType.PRESS_END)
            elif event_code == MS220_EVENT_BUTTON_DOUBLE:
                self._trigger_event(
                    ButtonEventType.MULTI_PRESS_END,
                    {ATTR_MULTI_PRESS_COUNT: 2},
                )
        super()._handle_coordinator_update()


class MerossBLEMS220DoorbellEventEntity(MerossBLEEntity, EventEntity):
    """Doorbell mode ring events (report_event 0x06)."""

    _attr_translation_key = "doorbell"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = [DoorbellEventType.RING]

    def __init__(self, coordinator: MerossBLEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}-doorbell"

    @callback
    def _handle_coordinator_update(self) -> None:
        for _req_id, event_code in self.coordinator.last_new_events:
            if event_code == MS220_EVENT_DOORBELL:
                self._trigger_event(DoorbellEventType.RING)
        super()._handle_coordinator_update()


class MerossBLEMS700ButtonEventEntity(_MerossBLEEventEntity):
    """One of nine MS700 screen buttons; single click → press_end."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [ButtonEventType.PRESS_END]

    def __init__(
        self,
        coordinator: MerossBLEDataUpdateCoordinator,
        button_number: int,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._button_number = button_number
        self._attr_unique_id = f"{coordinator.base_unique_id}-button-{button_number}"
        self._attr_translation_key = "ms700_button"
        self._attr_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        label = _ms700_button_label(self.coordinator, self._button_number)
        if label != self._attr_name:
            self._attr_name = label
        screen_enable = self.parsed_data.get("screen_enable")
        new_events = self.coordinator.last_new_events
        for req_id, event_code in new_events:
            logical = ms700_logical_button(event_code)
            if logical != self._button_number:
                continue
            if screen_enable is not None and not ms700_button_enabled(
                self._button_number, screen_enable
            ):
                _LOGGER.debug(
                    "%s: skip disabled MS700 button=%s req_id=%s event=%#x",
                    self.coordinator.ble_device.address,
                    self._button_number,
                    req_id,
                    event_code,
                )
                continue
            _LOGGER.debug(
                "%s: MS700 press_end button=%s req_id=%s event=%#x",
                self.coordinator.ble_device.address,
                self._button_number,
                req_id,
                event_code,
            )
            self._trigger_event(ButtonEventType.PRESS_END)
            self.async_write_ha_state()
            return
        super()._handle_coordinator_update()
