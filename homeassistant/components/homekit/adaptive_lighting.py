"""Apple Adaptive Lighting (HAP value-transition characteristics) for the HomeKit bridge.

The wire format and the transition maths are not documented by Apple. Both are
ported from the reference implementation in HAP-NodeJS, which is what Homebridge
plugins use:
https://github.com/homebridge/HAP-NodeJS/blob/latest/src/lib/controller/AdaptiveLightingController.ts
"""

import base64
from dataclasses import dataclass
from datetime import timedelta
import logging
import math
import struct
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import LightEntityStateAttribute
from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from pyhap.service import Service

    from .type_lights import Light

_LOGGER = logging.getLogger(__name__)

CHAR_ACTIVE_TRANSITION_COUNT = "ActiveTransitionCount"
CHAR_TRANSITION_CONTROL = "TransitionControl"
CHAR_SUPPORTED_TRANSITION_CONFIGURATION = "SupportedTransitionConfiguration"

ADAPTIVE_LIGHTING_CHARS = (
    CHAR_ACTIVE_TRANSITION_COUNT,
    CHAR_TRANSITION_CONTROL,
    CHAR_SUPPORTED_TRANSITION_CONFIGURATION,
)

EMPTY_TLV_TYPE = 0x00

# SupportedCharacteristicValueTransitionConfigurations
TAG_SUPPORTED_TRANSITION_CONFIGURATION = 0x01
TAG_CHARACTERISTIC_IID = 0x01
TAG_TRANSITION_TYPE = 0x02
TRANSITION_TYPE_BRIGHTNESS = 0x01
TRANSITION_TYPE_COLOR_TEMPERATURE = 0x02

# TransitionControl
TAG_READ_CURRENT_TRANSITION = 0x01
TAG_UPDATE_TRANSITION = 0x02

# ValueTransitionConfiguration
TAG_CFG_IID = 0x01
TAG_CFG_PARAMETERS = 0x02
TAG_CFG_UNKNOWN_3 = 0x03
TAG_CFG_CURVE = 0x05
TAG_CFG_UPDATE_INTERVAL = 0x06
TAG_CFG_NOTIFY_THRESHOLD = 0x08

# ValueTransitionParameters
TAG_PARAM_TRANSITION_ID = 0x01
TAG_PARAM_START_TIME = 0x02

# TransitionCurveConfiguration
TAG_CURVE_ENTRY = 0x01
TAG_CURVE_ADJUSTMENT_IID = 0x02
TAG_CURVE_MULTIPLIER_RANGE = 0x03
TAG_RANGE_MIN = 0x01
TAG_RANGE_MAX = 0x02

# TransitionEntry
TAG_ENTRY_ADJUSTMENT_FACTOR = 0x01
TAG_ENTRY_VALUE = 0x02
TAG_ENTRY_TRANSITION_OFFSET = 0x03
TAG_ENTRY_DURATION = 0x04

# ValueTransitionConfigurationResponse
TAG_RESPONSE_STATUS = 0x01
TAG_STATUS_IID = 0x01
TAG_STATUS_PARAMETERS = 0x02
TAG_STATUS_TIME_SINCE_START = 0x03

# HAP timestamps count from 2001-01-01, the Unix epoch counts from 1970-01-01.
EPOCH_MILLIS_2001 = 978307200000

# An update interval of zero would reschedule the timer immediately forever.
MIN_UPDATE_INTERVAL = 1000


def write_variable_uint_le(value: int) -> bytes:
    """Encode an unsigned int in the smallest little-endian width HAP accepts."""
    if value < 0:
        raise ValueError("value must not be negative")
    if value <= 0xFF:
        return value.to_bytes(1, "little")
    if value <= 0xFFFF:
        return value.to_bytes(2, "little")
    if value <= 0xFFFFFFFF:
        return value.to_bytes(4, "little")
    raise ValueError("value does not fit in 32 bits")


def read_variable_uint_le(value: bytes) -> int:
    """Decode a variable width little-endian unsigned int."""
    return int.from_bytes(value, "little")


def tlv_encode(*args: int | bytes) -> bytes:
    """Encode tag/value pairs, splitting values longer than 255 bytes."""
    if len(args) % 2:
        raise ValueError("expected an even number of arguments")
    out = bytearray()
    for index in range(0, len(args), 2):
        tag = args[index]
        value = args[index + 1]
        if not isinstance(tag, int) or not isinstance(value, bytes):
            raise TypeError("expected int tag and bytes value")
        if not value:
            out += bytes((tag, 0))
            continue
        for offset in range(0, len(value), 255):
            chunk = value[offset : offset + 255]
            out += bytes((tag, len(chunk))) + chunk
    return bytes(out)


def tlv_encode_list(tag: int, entries: list[bytes]) -> bytes:
    """Encode repeated entries under one tag, separated by the empty-TLV delimiter."""
    if not entries:
        return bytes((tag, 0))
    parts: list[bytes] = []
    for position, entry in enumerate(entries):
        if position:
            parts.append(bytes((EMPTY_TLV_TYPE, 0)))
        parts.append(tlv_encode(tag, entry))
    return b"".join(parts)


def tlv_decode(buffer: bytes) -> list[tuple[int, bytes]]:
    """Decode TLV8, joining the 255 byte chunks a long value was split into."""
    entries: list[tuple[int, bytes]] = []
    index = 0
    while index + 1 < len(buffer):
        tag = buffer[index]
        length = buffer[index + 1]
        if index + 2 + length > len(buffer):
            raise ValueError("TLV value is longer than the remaining buffer")
        value = buffer[index + 2 : index + 2 + length]
        index += 2 + length
        if (
            entries
            and entries[-1][0] == tag
            and entries[-1][1]
            and len(entries[-1][1]) % 255 == 0
        ):
            entries[-1] = (tag, entries[-1][1] + value)
        else:
            entries.append((tag, value))
    return entries


def tlv_first(entries: list[tuple[int, bytes]], tag: int) -> bytes | None:
    """Return the first value for a tag, or None."""
    return next((value for entry_tag, value in entries if entry_tag == tag), None)


def supported_transition_configuration(
    brightness_iid: int, color_temperature_iid: int
) -> str:
    """Build the base64 value advertising which characteristics support transitions."""
    return base64.b64encode(
        tlv_encode_list(
            TAG_SUPPORTED_TRANSITION_CONFIGURATION,
            [
                tlv_encode(
                    TAG_CHARACTERISTIC_IID,
                    write_variable_uint_le(brightness_iid),
                    TAG_TRANSITION_TYPE,
                    bytes((TRANSITION_TYPE_BRIGHTNESS,)),
                ),
                tlv_encode(
                    TAG_CHARACTERISTIC_IID,
                    write_variable_uint_le(color_temperature_iid),
                    TAG_TRANSITION_TYPE,
                    bytes((TRANSITION_TYPE_COLOR_TEMPERATURE,)),
                ),
            ],
        )
    ).decode()


@dataclass(slots=True)
class CurveEntry:
    """One point of the 24 hour schedule Apple sends."""

    temperature: float  # mireds
    brightness_adjustment_factor: float
    transition_time: int  # milliseconds since the previous entry
    duration: int  # milliseconds this value is held before interpolating


@dataclass(slots=True)
class ActiveTransition:
    """The schedule currently driving a light."""

    transition_id: bytes
    parameters: bytes
    start_millis: int  # unix millis, in the controller's clock
    time_millis_offset: int  # our clock minus the controller's clock
    curve: list[CurveEntry]
    update_interval: int
    notify_threshold: int
    min_multiplier: int
    max_multiplier: int


def parse_transition_control(value: str) -> ActiveTransition | None:
    """Parse an UpdateValueTransitionConfiguration write from the Home app."""
    update = tlv_first(tlv_decode(base64.b64decode(value)), TAG_UPDATE_TRANSITION)
    if not update:
        return None
    return parse_transition_update(update)


def parse_transition_update(update: bytes) -> ActiveTransition | None:
    """Parse the VALUE_TRANSITION_CONFIGURATION payload of an update write."""
    configuration = tlv_decode(tlv_decode(update)[0][1])
    parameters_raw = tlv_first(configuration, TAG_CFG_PARAMETERS)
    curve_raw = tlv_first(configuration, TAG_CFG_CURVE)
    if not parameters_raw or not curve_raw:
        return None

    parameters = tlv_decode(parameters_raw)
    start_time = tlv_first(parameters, TAG_PARAM_START_TIME)
    transition_id = tlv_first(parameters, TAG_PARAM_TRANSITION_ID)
    if not start_time or not transition_id:
        return None
    start_millis = struct.unpack("<Q", start_time)[0] + EPOCH_MILLIS_2001

    curve_entries = tlv_decode(curve_raw)
    curve: list[CurveEntry] = []
    for tag, raw in curve_entries:
        if tag != TAG_CURVE_ENTRY:
            continue
        entry = tlv_decode(raw)
        factor = tlv_first(entry, TAG_ENTRY_ADJUSTMENT_FACTOR)
        value_raw = tlv_first(entry, TAG_ENTRY_VALUE)
        if not factor or not value_raw:
            _LOGGER.warning("Adaptive lighting curve entry is incomplete")
            continue
        temperature = struct.unpack("<f", value_raw)[0]
        adjustment_factor = struct.unpack("<f", factor)[0]
        if not math.isfinite(temperature) or not math.isfinite(adjustment_factor):
            raise ValueError("adaptive lighting curve entry is not finite")
        offset_raw = tlv_first(entry, TAG_ENTRY_TRANSITION_OFFSET)
        duration_raw = tlv_first(entry, TAG_ENTRY_DURATION)
        # On the wire the duration of an entry is the hold time of the
        # *previous* curve point, matching the reference implementation.
        if curve and duration_raw:
            curve[-1].duration = read_variable_uint_le(duration_raw)
        curve.append(
            CurveEntry(
                temperature=temperature,
                brightness_adjustment_factor=adjustment_factor,
                transition_time=read_variable_uint_le(offset_raw) if offset_raw else 0,
                duration=0,
            )
        )
    if len(curve) < 2:
        return None

    min_multiplier, max_multiplier = 10, 100
    if multiplier_raw := tlv_first(curve_entries, TAG_CURVE_MULTIPLIER_RANGE):
        multiplier = tlv_decode(multiplier_raw)
        if (raw_min := tlv_first(multiplier, TAG_RANGE_MIN)) is not None:
            min_multiplier = read_variable_uint_le(raw_min)
        if (raw_max := tlv_first(multiplier, TAG_RANGE_MAX)) is not None:
            max_multiplier = read_variable_uint_le(raw_max)

    update_interval_raw = tlv_first(configuration, TAG_CFG_UPDATE_INTERVAL)
    notify_threshold_raw = tlv_first(configuration, TAG_CFG_NOTIFY_THRESHOLD)

    now_millis = int(time.time() * 1000)
    return ActiveTransition(
        transition_id=transition_id,
        parameters=parameters_raw,
        start_millis=start_millis,
        time_millis_offset=now_millis - start_millis,
        curve=curve,
        update_interval=(
            max(MIN_UPDATE_INTERVAL, read_variable_uint_le(update_interval_raw))
            if update_interval_raw
            else 60000
        ),
        notify_threshold=(
            read_variable_uint_le(notify_threshold_raw)
            if notify_threshold_raw
            else 600000
        ),
        min_multiplier=min_multiplier,
        max_multiplier=max_multiplier,
    )


def interpolate_point(
    transition: ActiveTransition, now_millis: int
) -> tuple[float, float] | None:
    """Return (mired, brightness adjustment factor) for this moment.

    Both values are interpolated between the two surrounding curve points, so
    the factor does not jump when the curve moves on to the next point. None is
    returned past the end of the curve.
    """
    offset = now_millis - transition.time_millis_offset - transition.start_millis
    if offset < 0:
        return None

    lower_bound_time_offset = 0
    for index in range(len(transition.curve) - 1):
        lower = transition.curve[index]
        upper = transition.curve[index + 1]
        lower_bound_time_offset += lower.transition_time
        if offset >= lower_bound_time_offset:
            if (
                offset
                <= lower_bound_time_offset + lower.duration + upper.transition_time
            ):
                transition_offset = offset - lower_bound_time_offset
                if lower.duration and transition_offset <= lower.duration:
                    return lower.temperature, lower.brightness_adjustment_factor
                if not upper.transition_time:
                    return upper.temperature, upper.brightness_adjustment_factor
                percentage = (
                    transition_offset - lower.duration
                ) / upper.transition_time
                return (
                    lower.temperature
                    + (upper.temperature - lower.temperature) * percentage,
                    lower.brightness_adjustment_factor
                    + (
                        upper.brightness_adjustment_factor
                        - lower.brightness_adjustment_factor
                    )
                    * percentage,
                )
        lower_bound_time_offset += lower.duration
    return None


def interpolate(transition: ActiveTransition, now_millis: int) -> float | None:
    """Return the mired value for this moment, or None past the end of the curve."""
    point = interpolate_point(transition, now_millis)
    return None if point is None else point[0]


STORAGE_KEY = "homekit.adaptive_lighting"
STORAGE_VERSION = 2
DATA_STORE = "homekit_adaptive_lighting_store"


def _transition_as_dict(transition: ActiveTransition) -> dict[str, Any]:
    """Serialise a transition so it survives a restart."""
    return {
        "transition_id": transition.transition_id.hex(),
        "parameters": transition.parameters.hex(),
        "start_millis": transition.start_millis,
        "time_millis_offset": transition.time_millis_offset,
        "update_interval": transition.update_interval,
        "notify_threshold": transition.notify_threshold,
        "min_multiplier": transition.min_multiplier,
        "max_multiplier": transition.max_multiplier,
        "curve": [
            [
                entry.temperature,
                entry.brightness_adjustment_factor,
                entry.transition_time,
                entry.duration,
            ]
            for entry in transition.curve
        ],
    }


def _transition_from_dict(data: dict[str, Any]) -> ActiveTransition:
    """Rebuild a stored transition."""
    return ActiveTransition(
        transition_id=bytes.fromhex(data["transition_id"]),
        parameters=bytes.fromhex(data["parameters"]),
        start_millis=data["start_millis"],
        time_millis_offset=data["time_millis_offset"],
        curve=[CurveEntry(*entry) for entry in data["curve"]],
        update_interval=data["update_interval"],
        notify_threshold=data["notify_threshold"],
        min_multiplier=data["min_multiplier"],
        max_multiplier=data["max_multiplier"],
    )


def _store_key(entry_id: str, entity_id: str) -> str:
    """Schedules are scoped to the HomeKit config entry that owns the accessory."""
    return f"{entry_id}/{entity_id}"


class _TransitionStore:
    """One store shared by every adaptive lighting accessory."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching disk yet."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    async def _async_load(self) -> dict[str, Any]:
        """Load the stored transitions once, keeping concurrent waiters on one dict."""
        if self._data is None:
            data = await self._store.async_load() or {}
            if self._data is None:
                self._data = data
        return self._data

    async def async_get(self, entry_id: str, entity_id: str) -> dict[str, Any] | None:
        """Return the stored transition for an entity, if any."""
        return (await self._async_load()).get(_store_key(entry_id, entity_id))

    async def async_set(
        self, entry_id: str, entity_id: str, data: dict[str, Any] | None
    ) -> None:
        """Store or drop the transition of an entity."""
        transitions = await self._async_load()
        key = _store_key(entry_id, entity_id)
        if data is None:
            transitions.pop(key, None)
        else:
            transitions[key] = data
        await self._store.async_save(transitions)

    async def async_delete_entry(self, entry_id: str) -> None:
        """Drop every stored transition of a removed HomeKit config entry."""
        transitions = await self._async_load()
        prefix = f"{entry_id}/"
        kept = {
            key: value
            for key, value in transitions.items()
            if not key.startswith(prefix)
        }
        if len(kept) != len(transitions):
            self._data = kept
            await self._store.async_save(kept)


def _get_store(hass: HomeAssistant) -> _TransitionStore:
    """Return the shared store, creating it on first use."""
    if DATA_STORE not in hass.data:
        hass.data[DATA_STORE] = _TransitionStore(hass)
    store: _TransitionStore = hass.data[DATA_STORE]
    return store


async def async_delete_stored_schedule(
    hass: HomeAssistant, entry_id: str, entity_id: str
) -> None:
    """Drop a persisted schedule for an entity no longer using adaptive lighting."""
    store = _get_store(hass)
    if await store.async_get(entry_id, entity_id) is not None:
        await store.async_set(entry_id, entity_id, None)


async def async_delete_entry_schedules(hass: HomeAssistant, entry_id: str) -> None:
    """Drop every persisted schedule of a removed HomeKit config entry."""
    if DATA_STORE in hass.data:
        await _get_store(hass).async_delete_entry(entry_id)


class AdaptiveLightingController:
    """Drive one Lightbulb service from the schedule the Home app sends.

    Apple computes the curve; this only decodes it, interpolates the current
    point every update interval and writes the result to the light.
    """

    def __init__(self, accessory: Light, service: Service, entity_id: str) -> None:
        """Wire the transition characteristics of a configured Lightbulb service."""
        self.accessory = accessory
        self.hass = accessory.hass
        self.entity_id = entity_id
        self._entry_id = accessory.driver.entry_id
        self.transition: ActiveTransition | None = None
        self.applying = False
        self._stopped = False
        self._last_applied: int | None = None
        self._cancel_updates: Any = None
        self._cancel_state: Any = None

        self.char_brightness = service.get_characteristic("Brightness")
        self.char_color_temp = service.get_characteristic("ColorTemperature")
        self.char_supported = service.get_characteristic(
            CHAR_SUPPORTED_TRANSITION_CONFIGURATION
        )
        self.char_supported.set_value(
            supported_transition_configuration(
                self.char_brightness.to_HAP()["iid"],
                self.char_color_temp.to_HAP()["iid"],
            )
        )
        self.char_active_count = service.get_characteristic(
            CHAR_ACTIVE_TRANSITION_COUNT
        )
        self.char_active_count.set_value(0)
        self.char_control = service.get_characteristic(CHAR_TRANSITION_CONTROL)
        self.char_control.setter_callback = self._handle_transition_control_write
        # Reads rebuild the status so the elapsed time is not frozen at arm.
        self.char_control.getter_callback = self._build_control_response
        self.char_control.set_value("")

    def _schedule(self, coro: Any) -> None:
        """Run a coroutine on the event loop.

        The accessory driver shares the Home Assistant loop, so the setter
        callbacks and Accessory.run already run on it.
        """
        self.hass.async_create_task(coro)

    @callback
    def _handle_transition_control_write(self, value: str) -> str | None:
        """Start, renew or stop the schedule the Home app just wrote.

        Returns the base64 TLV8 acknowledgement the controller expects back.
        """
        if not value:
            self.disable("Home app cleared the transition")
            return None

        try:
            request = tlv_decode(base64.b64decode(value))
        except ValueError:
            _LOGGER.exception(
                "%s: could not decode the transition request", self.entity_id
            )
            return None

        responses: list[bytes] = []
        for tag, raw in request:
            if tag == TAG_READ_CURRENT_TRANSITION:
                if response := self._build_read_response(raw):
                    responses.append(tlv_encode(TAG_READ_CURRENT_TRANSITION, response))
            elif (
                tag == TAG_UPDATE_TRANSITION
                and (response := self._handle_update_write(raw)) is not None
            ):
                responses.append(response)

        # client_update_value stored the raw request as the characteristic
        # value; put the status of the running transition back.
        self.char_control.value = self._build_control_response()
        if not responses:
            return None
        return base64.b64encode(b"".join(responses)).decode()

    @callback
    def _handle_update_write(self, update: bytes) -> bytes | None:
        """Arm, renew or disable the schedule carried by an update write."""
        try:
            configuration = tlv_decode(tlv_decode(update)[0][1])
        except IndexError, ValueError, struct.error:
            _LOGGER.exception("%s: malformed transition update", self.entity_id)
            return None

        unknown_3 = tlv_first(configuration, TAG_CFG_UNKNOWN_3)
        if not unknown_3 or unknown_3[0] == 0:
            # Like the reference implementation, an update without the
            # always-one marker is how the Home app disables adaptive
            # lighting.
            self.disable("Home app sent no transition configuration")
            return tlv_encode(TAG_UPDATE_TRANSITION, b"")

        try:
            transition = parse_transition_update(update)
        except ValueError, struct.error, IndexError:
            _LOGGER.exception(
                "%s: could not parse the transition schedule", self.entity_id
            )
            return None

        if transition is None:
            _LOGGER.warning(
                "%s: transition schedule is incomplete, keeping the current one",
                self.entity_id,
            )
            return None

        self._arm(transition)
        return tlv_encode(TAG_UPDATE_TRANSITION, self._status_tlv())

    def _build_read_response(self, read_request: bytes) -> bytes | None:
        """Rebuild the stored schedule for a read-current-transition request."""
        transition = self.transition
        if transition is None:
            return None

        read_entries = tlv_decode(read_request)
        if not read_entries:
            return None
        if (
            requested_iid := tlv_first(read_entries, TAG_CHARACTERISTIC_IID)
        ) is not None:
            if (
                read_variable_uint_le(requested_iid)
                != self.char_color_temp.to_HAP()["iid"]
            ):
                _LOGGER.warning(
                    "%s: read request for an unknown characteristic iid",
                    self.entity_id,
                )
                return None

        curve_entries = []
        previous_duration = 0
        for entry in transition.curve:
            curve_entries.append(
                tlv_encode(
                    TAG_ENTRY_ADJUSTMENT_FACTOR,
                    struct.pack("<f", entry.brightness_adjustment_factor),
                    TAG_ENTRY_VALUE,
                    struct.pack("<f", entry.temperature),
                    TAG_ENTRY_TRANSITION_OFFSET,
                    write_variable_uint_le(entry.transition_time),
                    TAG_ENTRY_DURATION,
                    write_variable_uint_le(previous_duration),
                )
            )
            previous_duration = entry.duration

        return tlv_encode(
            TAG_CFG_IID,
            write_variable_uint_le(self.char_color_temp.to_HAP()["iid"]),
            TAG_CFG_PARAMETERS,
            transition.parameters,
            TAG_CFG_UNKNOWN_3,
            b"\x01",
            TAG_CFG_CURVE,
            tlv_encode_list(TAG_CURVE_ENTRY, curve_entries)
            + tlv_encode(
                TAG_CURVE_ADJUSTMENT_IID,
                write_variable_uint_le(self.char_brightness.to_HAP()["iid"]),
                TAG_CURVE_MULTIPLIER_RANGE,
                tlv_encode(
                    TAG_RANGE_MIN,
                    write_variable_uint_le(transition.min_multiplier),
                    TAG_RANGE_MAX,
                    write_variable_uint_le(transition.max_multiplier),
                ),
            ),
            TAG_CFG_UPDATE_INTERVAL,
            write_variable_uint_le(transition.update_interval),
            TAG_CFG_NOTIFY_THRESHOLD,
            write_variable_uint_le(transition.notify_threshold),
        )

    @callback
    def _arm(self, transition: ActiveTransition, persist: bool = True) -> None:
        """Start applying a schedule, whether it just arrived or was restored."""
        self._stopped = False
        self.transition = transition
        self.char_active_count.set_value(1)
        self.char_control.value = self._build_control_response()
        _LOGGER.debug(
            "%s: adaptive lighting enabled, %d curve points, updating every %ds",
            self.entity_id,
            len(transition.curve),
            transition.update_interval // 1000,
        )

        if self._cancel_updates:
            self._cancel_updates()
        self._cancel_updates = async_track_time_interval(
            self.hass,
            self._async_update,
            timedelta(milliseconds=transition.update_interval),
        )
        if self._cancel_state:
            self._cancel_state()
        self._cancel_state = async_track_state_change_event(
            self.hass, [self.entity_id], self._handle_state_change
        )
        self._schedule(self._async_update())
        if persist:
            self._schedule(
                _get_store(self.hass).async_set(
                    self._entry_id,
                    self.entity_id,
                    _transition_as_dict(transition),
                )
            )

    def schedule_restore(self) -> None:
        """Queue the restore from the pyhap thread that starts the accessory."""
        self._schedule(self.async_restore())

    async def async_restore(self) -> None:
        """Resume the schedule saved before the last restart."""
        if self._stopped or self.transition:
            return
        stored = await _get_store(self.hass).async_get(self._entry_id, self.entity_id)
        # The accessory may have been stopped or re-armed while the store
        # was loading; a pending restore must not override either.
        if self._stopped or self.transition or stored is None:
            return
        try:
            transition = _transition_from_dict(stored)
        except KeyError, TypeError, ValueError:
            _LOGGER.warning("%s: stored transition is unreadable", self.entity_id)
            await _get_store(self.hass).async_set(self._entry_id, self.entity_id, None)
            return

        if interpolate(transition, int(time.time() * 1000)) is None:
            # The schedule only covers 24 hours; the Home app sends a new one.
            _LOGGER.debug("%s: stored transition expired", self.entity_id)
            await _get_store(self.hass).async_set(self._entry_id, self.entity_id, None)
            return

        _LOGGER.debug("%s: restoring adaptive lighting after restart", self.entity_id)
        self._arm(transition, persist=False)

    def _status_tlv(self) -> bytes:
        """The ValueTransitionConfigurationResponse TLV of the running transition."""
        if not (transition := self.transition):
            return b""
        elapsed = (
            int(time.time() * 1000)
            - transition.time_millis_offset
            - transition.start_millis
        )
        return tlv_encode(
            TAG_RESPONSE_STATUS,
            tlv_encode(
                TAG_STATUS_IID,
                write_variable_uint_le(self.char_color_temp.to_HAP()["iid"]),
                TAG_STATUS_PARAMETERS,
                transition.parameters,
                TAG_STATUS_TIME_SINCE_START,
                write_variable_uint_le(max(0, elapsed)),
            ),
        )

    def _build_control_response(self) -> str:
        """Answer a control read with the status of the running transition."""
        return base64.b64encode(self._status_tlv()).decode()

    @callback
    def disable(self, reason: str) -> None:
        """Stop adaptive lighting, as Apple expects on any manual colour change."""
        if not self.transition:
            return
        _LOGGER.debug("%s: adaptive lighting disabled (%s)", self.entity_id, reason)
        self.transition = None
        self._last_applied = None
        self.stop()
        self.char_active_count.set_value(0)
        self.char_control.value = ""
        self._schedule(
            _get_store(self.hass).async_set(self._entry_id, self.entity_id, None)
        )

    @callback
    def stop(self) -> None:
        """Cancel the timers but keep the stored schedule.

        Called when the accessory is torn down on a bridge reload. Without it
        the old controller keeps writing with the old colour range forever.
        """
        self._stopped = True
        if self._cancel_updates:
            self._cancel_updates()
            self._cancel_updates = None
        if self._cancel_state:
            self._cancel_state()
            self._cancel_state = None

    @callback
    def notify_manual_change(self) -> None:
        """Called when something other than us writes colour or brightness."""
        if not self.applying:
            self.disable("manual colour change")

    @callback
    def discard_applied(self) -> None:
        """Forget the last colour sent, because the light never received it.

        Without this the next cycle would see the same curve point and skip
        the write, leaving the bulb on the old colour until the curve moves.
        """
        self._last_applied = None

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Apply the curve when the light changes, instead of a minute later.

        Apple shifts the colour with the brightness level, so switching the
        light on and changing its brightness both land on a new point of the
        curve. Waiting for the next interval leaves the light on the old
        colour for as long as that interval.
        """
        new_state = event.data["new_state"]
        if new_state is None or new_state.state != STATE_ON:
            # A bulb keeps its own colour while it is off, so the curve has to
            # be written again on the way back even if the point has not moved.
            self._last_applied = None
            return
        old_state = event.data["old_state"]
        if (
            old_state is not None
            and old_state.state == STATE_ON
            and old_state.attributes.get(LightEntityStateAttribute.BRIGHTNESS)
            == new_state.attributes.get(LightEntityStateAttribute.BRIGHTNESS)
        ):
            return
        self._schedule(self._async_update())

    async def _async_update(self, _now: Any = None) -> None:
        """Apply the point of the curve that belongs to this minute."""
        if self._stopped or not (transition := self.transition):
            return

        point = interpolate_point(transition, int(time.time() * 1000))
        if point is None:
            self.disable("reached the end of the curve")
            return
        temperature, adjustment_factor = point

        # Apple sends a factor that shifts the colour with the brightness level.
        brightness = self.char_brightness.value or transition.max_multiplier
        multiplier = min(
            transition.max_multiplier, max(transition.min_multiplier, brightness)
        )
        temperature += adjustment_factor * multiplier

        mireds = round(temperature)
        properties = self.char_color_temp.properties
        mireds = min(
            properties.get("maxValue", 500),
            max(properties.get("minValue", 140), mireds),
        )

        state = self.hass.states.get(self.entity_id)
        if state is None or state.state != STATE_ON:
            # Writing colour to a light that is off would turn it on.
            return
        # Compare against what we sent: the bulb reports back a slightly
        # different mired, so comparing to the characteristic never matches
        # and every cycle would send a redundant command over the LAN.
        if self._last_applied == mireds:
            return
        self._last_applied = mireds

        _LOGGER.debug(
            "%s: applying %d mireds (%d K) for brightness %d%%",
            self.entity_id,
            mireds,
            round(1_000_000 / mireds),
            multiplier,
        )
        self.applying = True
        try:
            self.accessory.async_set_adaptive_color_temperature(mireds)
        finally:
            self.applying = False
