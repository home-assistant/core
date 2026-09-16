"""Runtime for KNX entity links (bidirectional Home Assistant entity <-> KNX).

An entity link makes an existing Home Assistant entity behave like a KNX actuator: it sends
the entity state to KNX status group addresses and drives the entity via service calls when
a write telegram is received on a command group address. Command and status group addresses
are required to differ, so a bus-driven change is fed back on the status group address
without looping.

The outbound direction is built on `ExposeSensor`, which provides answering GroupValueRead
requests, cooldown and periodic sending.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any

from xknx import XKNX
from xknx.core.telegram_queue import TelegramQueue
from xknx.devices import ExposeSensor
from xknx.exceptions import ConversionError, CouldNotParseTelegram
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import (
    DeviceGroupAddress,
    IndividualAddress,
    parse_device_group_address,
)
from xknx.telegram.apci import GroupValueWrite

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers.event import async_track_state_change_event

from .channel import CHANNELS, ChannelDefinition
from .const import CONF_INVERT, CONF_RESPOND_TO_READ
from .storage.const import (
    CONF_COOLDOWN,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_WRITE,
    CONF_PERIODIC_SEND,
    CONF_SEND_ON_INIT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Channel:
    """Runtime state for a single entity-link channel."""

    definition: ChannelDefinition
    expose: ExposeSensor
    command_addresses: list[DeviceGroupAddress]


class KnxEntityLink:
    """Link a Home Assistant entity to KNX group addresses bidirectionally."""

    def __init__(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        entity_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the link from validated store configuration."""
        self.hass = hass
        self.xknx = xknx
        self.entity_id = entity_id
        self._remove_listener: Callable[[], None] | None = None
        self._telegram_cb: TelegramQueue.Callback | None = None
        self._invert: bool = config[CONF_INVERT]
        self._send_on_init: bool = config[CONF_SEND_ON_INIT]

        self._channels = [
            _Channel(
                definition=definition,
                expose=ExposeSensor(
                    xknx=xknx,
                    name=f"{entity_id} {definition.status_key}",
                    group_address=parse_device_group_address(
                        config[definition.status_key][CONF_GA_WRITE]
                    ),
                    respond_to_read=config[CONF_RESPOND_TO_READ],
                    value_type=definition.dpt,
                    cooldown=config[CONF_COOLDOWN],
                    periodic_send=config[CONF_PERIODIC_SEND],
                ),
                command_addresses=[
                    parse_device_group_address(address)
                    for address in (
                        config[definition.command_key][CONF_GA_STATE],
                        *config[definition.command_key][CONF_GA_PASSIVE],
                    )
                    if address is not None
                ],
            )
            for definition in CHANNELS[Platform(split_entity_id(entity_id)[0])]
        ]
        self._by_command: dict[DeviceGroupAddress, _Channel] = {
            address: channel
            for channel in self._channels
            for address in channel.command_addresses
        }

    @callback
    def async_register(self) -> None:
        """Register the state listener, the xknx devices and the telegram callback."""
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )
        for channel in self._channels:
            self.xknx.devices.async_add(channel.expose)
        if command_addresses := list(self._by_command):
            self._telegram_cb = self.xknx.telegram_queue.register_telegram_received_cb(
                self._telegram_received_cb,
                group_addresses=command_addresses,
                match_for_outgoing=False,
            )
        self.hass.async_create_task(
            self._async_handle_state(self.hass.states.get(self.entity_id))
        )

    @callback
    def async_remove(self) -> None:
        """Prepare for deletion."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        if self._telegram_cb is not None:
            self.xknx.telegram_queue.unregister_telegram_received_cb(self._telegram_cb)
            self._telegram_cb = None
        for channel in self._channels:
            self.xknx.devices.async_remove(channel.expose)

    def _apply_invert(self, value: Any) -> Any:
        """Invert boolean channel values; other value types are unaffected."""
        if self._invert and isinstance(value, bool):
            return not value
        return value

    async def _async_entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle a Home Assistant state change."""
        await self._async_handle_state(event.data["new_state"])

    async def _async_handle_state(self, state: State | None) -> None:
        """Send the Home Assistant state to the status group addresses (outbound)."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        for channel in self._channels:
            value = channel.definition.from_state(state)
            if value is None:
                continue
            value = self._apply_invert(value)
            try:
                if channel.expose.sensor_value.value is None and not self._send_on_init:
                    channel.expose.initialize_value(value)
                    continue
                await channel.expose.set(value, skip_unchanged=True)
            except ConversionError as err:
                _LOGGER.warning(
                    "Could not encode %s for KNX entity link %s: %s",
                    channel.definition.status_key,
                    self.entity_id,
                    err,
                )

    @callback
    def _telegram_received_cb(self, telegram: Telegram) -> None:
        """Drive the Home Assistant entity from an incoming KNX write (inbound)."""
        if telegram.direction is not TelegramDirection.INCOMING:
            return
        if (
            not isinstance(telegram.payload, GroupValueWrite)
            or telegram.payload.value is None
            # group writes never target an individual address; narrows the lookup key
            or isinstance(telegram.destination_address, IndividualAddress)
        ):
            return
        channel = self._by_command.get(telegram.destination_address)
        if channel is None:
            return
        try:
            decoded = channel.definition.dpt.from_knx(telegram.payload.value)
        except (ConversionError, CouldNotParseTelegram) as err:
            _LOGGER.warning(
                "Could not decode incoming telegram for KNX entity link %s: %s",
                self.entity_id,
                err,
            )
            return
        # enum members are truthy regardless of their value - unwrap before use
        value = decoded.value if isinstance(decoded, Enum) else decoded
        call = channel.definition.to_service_call(
            self.entity_id, self._apply_invert(value)
        )
        if call is None:
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                call.domain, call.service, call.data, blocking=False
            ),
            f"KNX entity link {self.entity_id}",
        )
