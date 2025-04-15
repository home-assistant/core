"""Support for RFXtrx devices."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import RFXtrx as rfxtrxmod

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import DeviceTuple
from .const import ATTR_EVENT, COMMAND_GROUP_LIST, DATA_RFXOBJECT, DOMAIN, SIGNAL_EVENT


def _get_identifiers_from_device_tuple(
    device_tuple: DeviceTuple,
) -> set[tuple[str, str]]:
    """Calculate the device identifier from a device tuple."""
    # work around legacy identifier, being a multi tuple value
    return {(DOMAIN, *device_tuple)}  # type: ignore[arg-type]


class RfxtrxEntity(RestoreEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _device: rfxtrxmod.RFXtrxDevice
    _event: rfxtrxmod.RFXtrxEvent | None

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        event: rfxtrxmod.RFXtrxEvent | None = None,
    ) -> None:
        """Initialize the device."""
        self._attr_device_info = DeviceInfo(
            identifiers=_get_identifiers_from_device_tuple(device_id),
            model=device.type_string,
            name=f"{device.type_string} {device_id.id_string}",
        )
        self._attr_unique_id = "_".join(x for x in device_id)
        self._device = device
        self._event = event
        self._device_id = device_id
        # If id_string is 213c7f2:1, the group_id is 213c7f2, and the device will respond to
        # group events regardless of their group indices.
        (self._group_id, _, _) = device_id.id_string.partition(":")

    async def async_added_to_hass(self) -> None:
        """Restore RFXtrx device state (ON/OFF)."""
        if self._event:
            self._apply_event(self._event)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_EVENT, self._handle_event)
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device state attributes."""
        if not self._event:
            return None
        return {ATTR_EVENT: "".join(f"{x:02x}" for x in self._event.data)}

    def _event_applies(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> bool:
        """Check if event applies to me."""
        if isinstance(event, rfxtrxmod.ControlEvent):
            if (
                "Command" in event.values
                and event.values["Command"] in COMMAND_GROUP_LIST
            ):
                device: rfxtrxmod.RFXtrxDevice = event.device
                (group_id, _, _) = cast(str, device.id_string).partition(":")
                return group_id == self._group_id

        # Otherwise, the event only applies to the matching device.
        return device_id == self._device_id

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply a received event."""
        self._event = event

    @callback
    def _handle_event(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> None:
        """Handle a reception of data, overridden by other classes."""


class RfxtrxCommandEntity(RfxtrxEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    _attr_name = None

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        event: rfxtrxmod.RFXtrxEvent | None = None,
    ) -> None:
        """Initialzie a switch or light device."""
        super().__init__(device, device_id, event=event)

    async def _async_send[*_Ts](
        self, fun: Callable[[rfxtrxmod.PySerialTransport, *_Ts], None], *args: *_Ts
    ) -> None:
        rfx_object: rfxtrxmod.Connect = self.hass.data[DOMAIN][DATA_RFXOBJECT]
        await self.hass.async_add_executor_job(fun, rfx_object.transport, *args)
