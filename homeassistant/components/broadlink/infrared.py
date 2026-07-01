"""Infrared platform for Broadlink remotes."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, override

from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from broadlink.remote import (
    data_to_pulses as _bl_data_to_pulses,
    pulses_to_data as _bl_pulses_to_data,
)

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .entity import BroadlinkEntity

if TYPE_CHECKING:
    from .device import BroadlinkDevice

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
LEARNING_POLL_INTERVAL = timedelta(seconds=1)


def _timings_to_broadlink_packet(timings: list[int]) -> bytes:
    """Convert signed microsecond timings to a Broadlink IR packet.

    Positive values are pulse (high) durations; negative values are space
    (low) durations. The Broadlink library's encoder expects absolute
    durations.
    """
    pulses = [abs(t) for t in timings]
    return _bl_pulses_to_data(pulses)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink infrared entities."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities(
        [
            BroadlinkInfraredEmitterEntity(device),
            BroadlinkInfraredReceiverEntity(device),
        ]
    )


class BroadlinkInfraredEmitterEntity(BroadlinkEntity, InfraredEmitterEntity):
    """Broadlink infrared emitter entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_emitter"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-emitter"

    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via the Broadlink device."""
        packet = _timings_to_broadlink_packet(command.get_raw_timings())
        try:
            await self._device.async_request(self._device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err


class BroadlinkInfraredReceiverEntity(BroadlinkEntity, InfraredReceiverEntity):
    """Broadlink infrared receiver entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_receiver"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-receiver"
        self._receive_lock = asyncio.Lock()
        self._unsub_receive: CALLBACK_TYPE | None = None
        self._subscriber_count = 0

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop IR receive polling."""
        self._async_stop_receiving()
        self._subscriber_count = 0
        await super().async_will_remove_from_hass()

    @callback
    def _start_receiving(self) -> None:
        """Start polling and enter learning mode."""
        if self._unsub_receive is not None:
            return

        self._unsub_receive = async_track_time_interval(
            self.hass,
            self._async_poll_received_signal,
            LEARNING_POLL_INTERVAL,
        )

    @callback
    def _async_stop_receiving(self) -> None:
        """Stop polling for received signals."""
        if self._unsub_receive is None:
            return

        self._unsub_receive()
        self._unsub_receive = None

    @override
    @callback
    def async_subscribe_received_signal(
        self,
        signal_callback: Callable[[InfraredReceivedSignal], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to received IR signals and start polling on first subscriber."""
        unsub = super().async_subscribe_received_signal(signal_callback)
        self._subscriber_count += 1

        if self._subscriber_count == 1:
            self._start_receiving()

        removed = False

        @callback
        def _remove_callback() -> None:
            nonlocal removed
            if removed:
                return
            removed = True
            unsub()
            if self._subscriber_count:
                self._subscriber_count -= 1
            if self._subscriber_count == 0:
                self._async_stop_receiving()

        return _remove_callback

    async def _async_enter_learning_mode(self) -> None:
        """Put the device in learning mode to receive the next signal."""
        try:
            await self._device.async_request(self._device.api.enter_learning)
        except (BroadlinkException, OSError) as err:
            _LOGGER.debug(
                "Failed to enter learning mode for %s: %s", self.entity_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="enter_learning_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _async_poll_received_signal(self, _: datetime) -> None:
        """Poll Broadlink for an IR packet and dispatch it when available."""
        if self._receive_lock.locked() or not self.available:
            return

        async with self._receive_lock:
            try:
                await self._async_enter_learning_mode()
            except HomeAssistantError as err:
                _LOGGER.debug(
                    "Failed to start infrared receive mode for %s: %s",
                    self.entity_id,
                    err,
                )

            try:
                packet = await self._device.async_request(self._device.api.check_data)
            except ReadError, StorageError:
                return
            except (BroadlinkException, OSError) as err:
                _LOGGER.debug(
                    "Failed to check received data for %s: %s", self.entity_id, err
                )
                return

            self._handle_received_ir_signal(packet)

    @callback
    def _handle_received_ir_signal(self, packet: bytes) -> None:
        """Decode a Broadlink IR packet and dispatch it."""
        try:
            pulses = _bl_data_to_pulses(packet)
        except ValueError as err:
            _LOGGER.debug("Failed to decode infrared signal packet: %s", err)
            return

        timings = [
            pulse if index % 2 == 0 else -pulse
            for index, pulse in enumerate(pulses)
            if pulse > 0
        ]
        if timings:
            self._handle_received_signal(InfraredReceivedSignal(timings=timings))
