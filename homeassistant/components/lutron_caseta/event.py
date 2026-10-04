"""Support for Lutron Caseta keypad and pico button press events."""

from typing import Any, override

from homeassistant.components.event import (
    ButtonEventType,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ACTION_PRESS, ACTION_RELEASE, SIGNAL_BUTTON_EVENT
from .device_trigger import LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP
from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry, LutronCasetaData
from .util import enumerate_buttons


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad button events."""
    data = config_entry.runtime_data

    # Unlike the outbound button platform, unnamed pico buttons stay enabled:
    # reporting presses is the whole purpose of these entities
    async_add_entities(
        LutronCasetaButtonEvent(hass, device, data, button_name, device_info)
        for device, button_name, _, device_info in enumerate_buttons(data)
    )


class LutronCasetaButtonEvent(LutronCasetaEntity, EventEntity):
    """Representation of a physical Lutron pico or keypad button."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_has_entity_name = True
    _pressed = False

    def __init__(
        self,
        hass: HomeAssistant,
        device: dict[str, Any],
        data: LutronCasetaData,
        button_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Init a button event entity."""
        super().__init__(hass, device, data)
        self._attr_name = button_name
        self._attr_device_info = device_info
        self._config_entry_id = data.config_entry_id
        # Picos report both press and release. Keypads only reliably report
        # the press: depending on the system, a physical keypad press sends
        # Press alone or Press and Release together. A device with one event
        # per interaction maps it to press_end, so that is all keypads declare.
        self._reports_release = device["type"] in LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP
        if self._reports_release:
            self._attr_event_types = [
                ButtonEventType.PRESS_START,
                ButtonEventType.PRESS_END,
            ]
        else:
            self._attr_event_types = [ButtonEventType.PRESS_END]

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_BUTTON_EVENT.format(self._config_entry_id, self.device_id),
                self._handle_action,
            )
        )

    @callback
    def _handle_action(self, action: str) -> None:
        """Translate a button action into a standard button event."""
        # MultiTap is not mapped: each tap still emits a press, as device triggers do.
        if action == ACTION_PRESS and self._reports_release:
            self._pressed = True
            self._trigger_event(ButtonEventType.PRESS_START)
        elif action == ACTION_PRESS:
            # A keypad release may never come, so fire on the press.
            self._trigger_event(ButtonEventType.PRESS_END)
        elif action == ACTION_RELEASE and self._pressed:
            # A release without a press is the bridge replaying status on reconnect.
            self._pressed = False
            self._trigger_event(ButtonEventType.PRESS_END)
        else:
            return
        self.async_write_ha_state()

    @property
    @override
    def serial(self) -> None:
        """Buttons shouldn't have serial numbers, Return None."""
        return None
