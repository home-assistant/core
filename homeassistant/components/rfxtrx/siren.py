"""Support for RFXtrx lights."""
from __future__ import annotations

from typing import Any, Final

import RFXtrx as rfxtrxmod

from homeassistant.components.siren import (
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SirenEntity,
)
from homeassistant.components.siren.const import ATTR_TONE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import (
    DEFAULT_SIGNAL_REPETITIONS,
    DeviceTuple,
    RfxtrxCommandEntity,
    async_setup_platform_entry,
)
from .const import CONF_SIGNAL_REPETITIONS

SUPPORT_RFXTRX = SUPPORT_TURN_ON | SUPPORT_TONES

SECURITY_PANIC_ON = "Panic"
SECURITY_PANIC_OFF = "End Panic"
SECURITY_PANIC_ALL = {SECURITY_PANIC_ON, SECURITY_PANIC_OFF}


def supported(event: rfxtrxmod.RFXtrxEvent):
    """Return whether an event supports switch."""
    device = event.device

    if isinstance(device, rfxtrxmod.ChimeDevice):
        return True

    if isinstance(device, rfxtrxmod.SecurityDevice) and isinstance(
        event, rfxtrxmod.SensorEvent
    ):
        if event.values["Sensor Status"] in SECURITY_PANIC_ALL:
            return True

    return False


def get_first_key(data: dict[int, str], entry: str) -> int:
    """Find a key based on the items value."""
    return next((key for key, value in data.items() if value == entry))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up config entry."""

    def _constructor(
        event: rfxtrxmod.RFXtrxEvent,
        auto: rfxtrxmod.RFXtrxEvent | None,
        device_id: DeviceTuple,
        entity_info: dict,
    ):
        """Construct a entity from an event."""
        device = event.device

        if isinstance(device, rfxtrxmod.ChimeDevice):
            return [
                RfxtrxChime(
                    event.device,
                    device_id,
                    entity_info.get(
                        CONF_SIGNAL_REPETITIONS, DEFAULT_SIGNAL_REPETITIONS
                    ),
                    auto,
                )
            ]

        if isinstance(device, rfxtrxmod.SecurityDevice) and isinstance(
            event, rfxtrxmod.SensorEvent
        ):
            if event.values["Sensor Status"] in SECURITY_PANIC_ALL:
                return [
                    RfxtrxSecurityPanic(
                        event.device,
                        device_id,
                        entity_info.get(
                            CONF_SIGNAL_REPETITIONS, DEFAULT_SIGNAL_REPETITIONS
                        ),
                        auto,
                    )
                ]
        return None

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxTimeoutMixin(Entity):
    """Mixin to support timeouts on data."""

    _timeout: CALLBACK_TYPE | None = None
    _timeout_seconds: Final = 2.0

    def _setup_timeout(self):
        @callback
        def _done(_):
            self._timeout = None
            self.async_write_ha_state()

        self._timeout = async_call_later(self.hass, self._timeout_seconds, _done)

    def _cancel_timeout(self):
        if self._timeout:
            self._timeout()
            self._timeout = None


class RfxtrxChime(RfxtrxCommandEntity, SirenEntity, RfxtrxTimeoutMixin):
    """Representation of a RFXtrx light."""

    _device: rfxtrxmod.ChimeDevice

    def __init__(self, device, device_id, signal_repetitions=1, event=None):
        """Initialzie a switch or light device."""
        super().__init__(device, device_id, signal_repetitions, event)
        self._attr_available_tones = list(self._device.COMMANDS.values())
        self._attr_supported_features = SUPPORT_TURN_ON | SUPPORT_TONES
        self._default_tone = next(iter(self._device.COMMANDS))

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._timeout is not None

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._cancel_timeout()

        if tone := kwargs.get(ATTR_TONE):
            command = get_first_key(self._device.COMMANDS, tone)
        else:
            command = self._default_tone

        await self._async_send(self._device.send_command, command)

        self._setup_timeout()

        self.async_write_ha_state()

    def _apply_event(self, event: rfxtrxmod.ControlEvent):
        """Apply a received event."""
        super()._apply_event(event)

        sound = event.values.get("Sound")
        if sound is not None:
            self._cancel_timeout()
            self._setup_timeout()

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if self._event_applies(event, device_id):
            self._apply_event(event)

            self.async_write_ha_state()


class RfxtrxSecurityPanic(RfxtrxCommandEntity, SirenEntity, RfxtrxTimeoutMixin):
    """Representation of a RFXtrx light."""

    _device: rfxtrxmod.SecurityDevice

    def __init__(self, device, device_id, signal_repetitions=1, event=None):
        """Initialzie a switch or light device."""
        super().__init__(device, device_id, signal_repetitions, event)
        self._attr_supported_features = SUPPORT_TURN_ON | SUPPORT_TURN_OFF
        self._on_value = get_first_key(self._device.STATUS, SECURITY_PANIC_ON)
        self._off_value = get_first_key(self._device.STATUS, SECURITY_PANIC_OFF)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._timeout is not None

    async def async_turn_on(self, **kwargs: Any):
        """Turn the device on."""
        self._cancel_timeout()

        await self._async_send(self._device.send_status, self._on_value)

        self._setup_timeout()

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._cancel_timeout()

        await self._async_send(self._device.send_status, self._off_value)

        self.async_write_ha_state()

    def _apply_event(self, event: rfxtrxmod.SensorEvent):
        """Apply a received event."""
        super()._apply_event(event)

        status = event.values.get("Sensor Status")

        if status == SECURITY_PANIC_ON:
            self._cancel_timeout()
            self._setup_timeout()
        elif status == SECURITY_PANIC_OFF:
            self._cancel_timeout()

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if self._event_applies(event, device_id):
            self._apply_event(event)

            self.async_write_ha_state()
