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
import struct
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ATTR_BRIGHTNESS
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
            continue
        offset_raw = tlv_first(entry, TAG_ENTRY_TRANSITION_OFFSET)
        duration_raw = tlv_first(entry, TAG_ENTRY_DURATION)
        curve.append(
            CurveEntry(
                temperature=struct.unpack("<f", value_raw)[0],
                brightness_adjustment_factor=struct.unpack("<f", factor)[0],
                transition_time=read_variable_uint_le(offset_raw) if offset_raw else 0,
                duration=read_variable_uint_le(duration_raw) if duration_raw else 0,
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
            read_variable_uint_le(update_interval_raw) if update_interval_raw else 60000
        ),
        notify_threshold=(
            read_variable_uint_le(notify_threshold_raw)
            if notify_threshold_raw
            else 600000
        ),
        min_multiplier=min_multiplier,
        max_multiplier=max_multiplier,
    )


def interpolate(transition: ActiveTransition, now_millis: int) -> float | None:
    """Return the mired value for this moment, or None past the end of the curve."""
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
                    return lower.temperature
                percentage = (
                    transition_offset - lower.duration
                ) / upper.transition_time
                return (
                    lower.temperature
                    + (upper.temperature - lower.temperature) * percentage
                )
        lower_bound_time_offset += lower.duration
    return None


STORAGE_KEY = "homekit.adaptive_lighting"
STORAGE_VERSION = 1
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


class _TransitionStore:
    """One store shared by every adaptive lighting accessory."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching disk yet."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    async def async_get(self, entity_id: str) -> dict[str, Any] | None:
        """Return the stored transition for an entity, if any."""
        if self._data is None:
            self._data = await self._store.async_load() or {}
        return self._data.get(entity_id)

    async def async_set(self, entity_id: str, data: dict[str, Any] | None) -> None:
        """Store or drop the transition of an entity."""
        if self._data is None:
            self._data = await self._store.async_load() or {}
        if data is None:
            self._data.pop(entity_id, None)
        else:
            self._data[entity_id] = data
        await self._store.async_save(self._data)


def _get_store(hass: HomeAssistant) -> _TransitionStore:
    """Return the shared store, creating it on first use."""
    if DATA_STORE not in hass.data:
        hass.data[DATA_STORE] = _TransitionStore(hass)
    store: _TransitionStore = hass.data[DATA_STORE]
    return store


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
        self.transition: ActiveTransition | None = None
        self.applying = False
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
        self.char_control.set_value("")

    def _schedule(self, coro: Any) -> None:
        """Run a coroutine on the event loop from any thread.

        pyhap calls the setter callbacks and Accessory.run from its own thread.
        """
        self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, coro)

    @callback
    def _handle_transition_control_write(self, value: str) -> None:
        """Start, renew or stop the schedule the Home app just wrote."""
        if not value:
            self.disable("Home app cleared the transition")
            return

        try:
            transition = parse_transition_control(value)
        except ValueError, struct.error, IndexError:
            _LOGGER.exception(
                "%s: could not parse the transition schedule", self.entity_id
            )
            return

        if transition is None:
            self.disable("Home app sent no transition configuration")
            return

        self._arm(transition)

    @callback
    def _arm(self, transition: ActiveTransition, persist: bool = True) -> None:
        """Start applying a schedule, whether it just arrived or was restored."""
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
                    self.entity_id, _transition_as_dict(transition)
                )
            )

    def schedule_restore(self) -> None:
        """Queue the restore from the pyhap thread that starts the accessory."""
        self._schedule(self.async_restore())

    async def async_restore(self) -> None:
        """Resume the schedule saved before the last restart."""
        if self.transition or not (
            stored := await _get_store(self.hass).async_get(self.entity_id)
        ):
            return
        try:
            transition = _transition_from_dict(stored)
        except KeyError, TypeError, ValueError:
            _LOGGER.warning("%s: stored transition is unreadable", self.entity_id)
            await _get_store(self.hass).async_set(self.entity_id, None)
            return

        if interpolate(transition, int(time.time() * 1000)) is None:
            # The schedule only covers 24 hours; the Home app sends a new one.
            _LOGGER.debug("%s: stored transition expired", self.entity_id)
            await _get_store(self.hass).async_set(self.entity_id, None)
            return

        _LOGGER.debug("%s: restoring adaptive lighting after restart", self.entity_id)
        self._arm(transition, persist=False)

    def _build_control_response(self) -> str:
        """Answer a control read with the status of the running transition."""
        if not (transition := self.transition):
            return ""
        elapsed = (
            int(time.time() * 1000)
            - transition.time_millis_offset
            - transition.start_millis
        )
        return base64.b64encode(
            tlv_encode(
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
        ).decode()

    @callback
    def disable(self, reason: str) -> None:
        """Stop adaptive lighting, as Apple expects on any manual colour change."""
        if not self.transition:
            return
        _LOGGER.debug("%s: adaptive lighting disabled (%s)", self.entity_id, reason)
        self.transition = None
        self._last_applied = None
        if self._cancel_updates:
            self._cancel_updates()
            self._cancel_updates = None
        if self._cancel_state:
            self._cancel_state()
            self._cancel_state = None
        self.char_active_count.set_value(0)
        self.char_control.value = ""
        self._schedule(_get_store(self.hass).async_set(self.entity_id, None))

    @callback
    def notify_manual_change(self) -> None:
        """Called when something other than us writes colour or brightness."""
        if not self.applying:
            self.disable("manual colour change")

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
            and old_state.attributes.get(ATTR_BRIGHTNESS)
            == new_state.attributes.get(ATTR_BRIGHTNESS)
        ):
            return
        self._schedule(self._async_update())

    async def _async_update(self, _now: Any = None) -> None:
        """Apply the point of the curve that belongs to this minute."""
        if not (transition := self.transition):
            return

        temperature = interpolate(transition, int(time.time() * 1000))
        if temperature is None:
            self.disable("reached the end of the curve")
            return

        # Apple sends a factor that shifts the colour with the brightness level.
        brightness = self.char_brightness.value or transition.max_multiplier
        multiplier = min(
            transition.max_multiplier, max(transition.min_multiplier, brightness)
        )
        point = self._current_curve_point(transition)
        if point is not None:
            temperature += point.brightness_adjustment_factor * multiplier

        mireds = round(temperature)
        properties = self.char_color_temp.properties
        mireds = min(
            properties.get("maxValue", 500),
            max(properties.get("minValue", 140), mireds),
        )

        state = self.hass.states.get(self.entity_id)
        if state is None or state.state != "on":
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

    def _current_curve_point(self, transition: ActiveTransition) -> CurveEntry | None:
        """Return the curve entry in effect right now, for its brightness factor."""
        offset = (
            int(time.time() * 1000)
            - transition.time_millis_offset
            - transition.start_millis
        )
        accumulated = 0
        for index in range(len(transition.curve) - 1):
            lower = transition.curve[index]
            accumulated += lower.transition_time
            if (
                accumulated
                <= offset
                <= accumulated
                + lower.duration
                + transition.curve[index + 1].transition_time
            ):
                return lower
            accumulated += lower.duration
        return None
