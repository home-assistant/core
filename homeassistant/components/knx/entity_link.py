"""Runtime for KNX entity links (bidirectional Home Assistant entity <-> KNX).

An entity link makes an existing Home Assistant entity behave like a KNX actuator: it sends
the entity state to KNX status group addresses and drives the entity via service calls when
a write telegram is received on a command group address. Command and status group addresses
are distinct, so a bus-driven change is fed back on the status GA without looping.
"""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from xknx import XKNX
from xknx.core.telegram_queue import TelegramQueue
from xknx.exceptions import ConversionError, CouldNotParseTelegram
from xknx.remote_value import RemoteValue
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import DeviceGroupAddress, IndividualAddress
from xknx.telegram.apci import GroupValueWrite

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .channel import CHANNELS, ChannelDefinition

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Channel:
    """Runtime state for a single entity-link channel."""

    role: str
    definition: ChannelDefinition
    remote_value: RemoteValue

    @property
    def command_addresses(self) -> list[DeviceGroupAddress]:
        """Group addresses the link listens on for incoming commands."""
        rv = self.remote_value
        addresses = list(rv.passive_group_addresses)
        if rv.group_address_state is not None:
            addresses.append(rv.group_address_state)
        return addresses


class KnxEntityLink:
    """Link a Home Assistant entity to KNX group addresses bidirectionally."""

    def __init__(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        entity_id: str,
        platform: str,
        channels_config: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize the link from validated store configuration."""
        self.hass = hass
        self.xknx = xknx
        self.entity_id = entity_id
        self._remove_listener: Callable[[], None] | None = None
        self._telegram_cb: TelegramQueue.Callback | None = None

        definitions = CHANNELS[Platform(platform)]
        self._channels: list[_Channel] = []
        for role, ga in channels_config.items():
            status_ga = ga.get("write")
            command_gas = [a for a in (ga.get("state"), *ga.get("passive", [])) if a]
            remote_value = definitions[role].remote_value_factory(
                xknx, status_ga, command_gas
            )
            self._channels.append(_Channel(role, definitions[role], remote_value))

        self._by_command: dict[DeviceGroupAddress, _Channel] = {
            address: channel
            for channel in self._channels
            for address in channel.command_addresses
        }

    @callback
    def async_register(self) -> None:
        """Register the state listener and the incoming-telegram callback."""
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )
        if command_addresses := list(self._by_command):
            self._telegram_cb = self.xknx.telegram_queue.register_telegram_received_cb(
                self._telegram_received_cb,
                group_addresses=command_addresses,
                match_for_outgoing=False,
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

    async def _async_entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Send the new Home Assistant state to KNX (outbound)."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        for channel in self._channels:
            if channel.remote_value.group_address is None:
                continue  # channel has no status address -> outbound disabled
            value = channel.definition.read_state(new_state)
            if value is None:
                continue
            try:
                payload = channel.remote_value.to_knx(value)
            except ConversionError as err:
                _LOGGER.warning(
                    "Could not encode %s for KNX entity link %s: %s",
                    channel.role,
                    self.entity_id,
                    err,
                )
                continue
            channel.remote_value.send_raw(payload)

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
            value = channel.remote_value.from_knx(telegram.payload.value)
        except (ConversionError, CouldNotParseTelegram) as err:
            _LOGGER.warning(
                "Could not decode incoming telegram for KNX entity link %s: %s",
                self.entity_id,
                err,
            )
            return
        call = channel.definition.to_service_call(self.entity_id, value)
        if call is None:
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                call.domain, call.service, call.data, blocking=False
            ),
            f"KNX entity link {self.entity_id}",
        )
