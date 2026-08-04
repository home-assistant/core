"""Infrared platform for Broadlink remotes."""

import asyncio
from contextlib import suppress
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SIGNAL_CAPTURE_IR
from .entity import BroadlinkEntity

if TYPE_CHECKING:
    from .device import BroadlinkDevice

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = 1
REARM_INTERVAL = timedelta(seconds=20)
ERROR_BACKOFF = 5
TRANSMIT_COOLDOWN = 0.3
CAPTURE_WINDOW = timedelta(seconds=15)
CAPTURE_LIMIT = timedelta(seconds=60)


def _timings_to_broadlink_packet(timings: list[int]) -> bytes:
    """Convert signed microsecond timings to a Broadlink IR packet.

    Positive values are pulse (high) durations; negative values are space
    (low) durations. The Broadlink library's encoder expects absolute
    durations.
    """
    pulses = [abs(t) for t in timings]
    return _bl_pulses_to_data(pulses)


def _broadlink_packet_to_timings(packet: bytes) -> list[int]:
    """Convert a Broadlink IR packet to signed microsecond timings.

    The device reports alternating durations starting with a pulse, while
    consumers expect pulses positive and spaces negative.
    """
    return [
        duration if index % 2 == 0 else -duration
        for index, duration in enumerate(_bl_data_to_pulses(packet))
    ]


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
            BroadlinkInfraredEntity(device),
            BroadlinkInfraredReceiverEntity(device, config_entry),
        ]
    )


class BroadlinkInfraredEntity(BroadlinkEntity, InfraredEmitterEntity):
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
        async with self._device.front_end.exclusive():
            try:
                await self._device.async_request(self._device.api.send_data, packet)
            except (BroadlinkException, OSError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="send_command_failed",
                    translation_placeholders={"error": str(err)},
                ) from err


class BroadlinkInfraredReceiverEntity(BroadlinkEntity, InfraredReceiverEntity):
    """Broadlink infrared receiver entity.

    The device cannot listen passively: it has to be held in learning mode and
    polled, which lights its LED and takes the front end away from
    `remote.learn_command`. It therefore only listens during a capture window
    that is opened on request, and reports itself unavailable the rest of the
    time, so consumers attach for a capture and let go again afterwards.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_receiver"

    def __init__(self, device: BroadlinkDevice, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-receiver"
        self._config_entry = config_entry
        self._listen_task: asyncio.Task[None] | None = None
        self._stop_listening = asyncio.Event()
        self._window_ends_at: datetime | None = None
        self._window_limit = dt_util.utcnow()

    @property
    @override
    def available(self) -> bool:
        """Return True while a capture window is open."""
        return super().available and self._window_ends_at is not None

    @override
    async def async_added_to_hass(self) -> None:
        """Listen for requests to open a capture window."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CAPTURE_IR.format(self._device.unique_id),
                self._async_open_window,
            )
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Wait for the listener to finish its current device request.

        Cancelling it would release the front end while a request is still
        running in the executor, leaving another platform free to talk to the
        device at the same time.
        """
        await super().async_will_remove_from_hass()
        self._stop_listening.set()
        if self._listen_task is not None:
            await self._listen_task

    @callback
    def _async_open_window(self) -> None:
        """Open a capture window, or start it over if one is already open."""
        now = dt_util.utcnow()
        self._window_limit = now + CAPTURE_LIMIT
        self._window_ends_at = now + CAPTURE_WINDOW
        self.async_write_ha_state()

        if self._listen_task is None and not self._stop_listening.is_set():
            self._listen_task = self._config_entry.async_create_background_task(
                self.hass,
                self._async_listen(),
                f"{self.entity_id} infrared receiver",
            )

    @callback
    def _async_extend_window(self) -> None:
        """Keep the window open while codes keep arriving, up to the limit."""
        self._window_ends_at = min(
            dt_util.utcnow() + CAPTURE_WINDOW, self._window_limit
        )

    @callback
    def _async_close_window(self) -> None:
        """Close the capture window, releasing any consumers."""
        self._window_ends_at = None
        self._listen_task = None
        self.async_write_ha_state()

    async def _async_idle(self, delay: float) -> None:
        """Wait between polls, returning early when removed."""
        with suppress(TimeoutError):
            await asyncio.wait_for(self._stop_listening.wait(), delay)

    async def _async_listen(self) -> None:
        """Capture IR signals until the window closes.

        A capture is only available while the learning session that recorded it
        is valid, so the session is renewed after every capture, whenever a
        transmission invalidated it, and before the device times it out.
        """
        device = self._device
        front_end = device.front_end
        armed_generation: int | None = None
        armed_until = dt_util.utcnow()

        while self._window_is_open() and not self._stop_listening.is_set():
            if (
                armed_generation is not None
                and armed_generation != front_end.generation
            ):
                # Give the repeat frames of the transmission that invalidated
                # our session time to pass, so we do not capture our own output.
                await asyncio.sleep(TRANSMIT_COOLDOWN)

            packet: bytes | None = None
            try:
                async with front_end.lock:
                    if (
                        armed_generation != front_end.generation
                        or armed_until <= dt_util.utcnow()
                    ):
                        await device.async_request(device.api.enter_learning)
                        armed_generation = front_end.generation
                        armed_until = dt_util.utcnow() + REARM_INTERVAL

                    try:
                        packet = await device.async_request(device.api.check_data)
                    except ReadError, StorageError:
                        packet = None

            except (BroadlinkException, OSError) as err:
                _LOGGER.debug("Failed to listen for IR signals: %s", err)
                armed_generation = None
                await self._async_idle(ERROR_BACKOFF)
                continue

            if packet is not None:
                armed_generation = None
                self._async_handle_packet(packet)

            await self._async_idle(POLL_INTERVAL)

        self._async_close_window()

    @callback
    def _window_is_open(self) -> bool:
        """Return True while the capture window has time left on it."""
        return (
            self._window_ends_at is not None and dt_util.utcnow() < self._window_ends_at
        )

    @callback
    def _async_handle_packet(self, packet: bytes) -> None:
        """Decode a captured packet and report it as a received signal."""
        try:
            timings = _broadlink_packet_to_timings(packet)
        except ValueError as err:
            _LOGGER.debug("Discarding malformed IR packet: %s", err)
            return

        self._async_extend_window()
        self._handle_received_signal(InfraredReceivedSignal(timings=timings))
