"""Support for RFXtrx sirens."""
from __future__ import annotations

from typing import Any

import RFXtrx as rfxtrxmod

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.components.siren.const import ATTR_TONE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import (
    DEFAULT_OFF_DELAY,
    DeviceTuple,
    RfxtrxCommandEntity,
    async_setup_platform_entry,
)
from .const import CONF_OFF_DELAY

SECURITY_PANIC_ON = "Panic"
SECURITY_PANIC_OFF = "End Panic"
SECURITY_PANIC_ALL = {SECURITY_PANIC_ON, SECURITY_PANIC_OFF}


def supported(event: rfxtrxmod.RFXtrxEvent):
    """Return whether an event supports sirens."""
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
                    entity_info.get(CONF_OFF_DELAY, DEFAULT_OFF_DELAY),
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
                        entity_info.get(CONF_OFF_DELAY, DEFAULT_OFF_DELAY),
                        auto,
                    )
                ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxOffDelayMixin(Entity):
    """Mixin to support timeouts on data.

    Many 433 devices only send data when active. They will
    repeatedly (every x seconds) send a command to indicate
    being active and stop sending this command when inactive.
    This mixin allow us to keep track of the timeout once
    they go inactive.
    """

    _timeout: CALLBACK_TYPE | None = None
    _off_delay: float | None = None

    def _setup_timeout(self):
        @callback
        def _done(_):
            self._timeout = None
            self.async_write_ha_state()

        if self._off_delay:
            self._timeout = async_call_later(self.hass, self._off_delay, _done)

    def _cancel_timeout(self):
        if self._timeout:
            self._timeout()
            self._timeout = None


class RfxtrxChime(RfxtrxCommandEntity, SirenEntity, RfxtrxOffDelayMixin):
    """Representation of a RFXtrx chime."""

    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TONES
    _device: rfxtrxmod.ChimeDevice

    def __init__(self, device, device_id, off_delay=None, event=None):
        """Initialize the entity."""
        super().__init__(device, device_id, event)
        self._attr_available_tones = list(self._device.COMMANDS.values())
        self._default_tone = next(iter(self._device.COMMANDS))
        self._off_delay = off_delay

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


class RfxtrxSecurityPanic(RfxtrxCommandEntity, SirenEntity, RfxtrxOffDelayMixin):
    """Representation of a security device."""

    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
    _device: rfxtrxmod.SecurityDevice

    def __init__(self, device, device_id, off_delay=None, event=None):
        """Initialize the entity."""
        super().__init__(device, device_id, event)
        self._on_value = get_first_key(self._device.STATUS, SECURITY_PANIC_ON)
        self._off_value = get_first_key(self._device.STATUS, SECURITY_PANIC_OFF)
        self._off_delay = off_delay

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
