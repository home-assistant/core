"""Test the adaptive lighting transition protocol of the HomeKit bridge."""

import base64
from datetime import timedelta
import time
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.homekit.adaptive_lighting import (
    CHAR_TRANSITION_CONTROL,
    DATA_STORE,
    TAG_CFG_CURVE,
    TAG_CFG_IID,
    TAG_CFG_PARAMETERS,
    TAG_CURVE_ENTRY,
    TAG_ENTRY_ADJUSTMENT_FACTOR,
    TAG_ENTRY_VALUE,
    TAG_PARAM_START_TIME,
    TAG_PARAM_TRANSITION_ID,
    TAG_UPDATE_TRANSITION,
    _get_store,
    _transition_as_dict,
    _transition_from_dict,
    interpolate,
    parse_transition_control,
    supported_transition_configuration,
    tlv_decode,
    tlv_encode,
    tlv_encode_list,
    write_variable_uint_le,
)
from homeassistant.components.homekit.const import (
    CHAR_COLOR_TEMPERATURE,
    CONF_ADAPTIVE_LIGHTING,
)
from homeassistant.components.homekit.type_lights import (
    CHANGE_COALESCE_TIME_WINDOW,
    Light,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service

# A real schedule written by the Home app to a colour temperature light. The
# curve covers 24 hours in 42 points and asks for an update every 60 seconds.
TRANSITION_CONTROL_WRITE = (
    "Av8B/wEBDQImARDE8z2pY8lMD4uJbDajPu+eAgiCLNrVvAAAAAMI7Ig7PwjVT4kDAQEF/wEP"
    "AQQXbEG/AgQcx/1DAwEAAAABEgEEMzMzvwIEAID9QwMEwLAHAAAAARIBBGzBFr8CBMdx+0MD"
    "BEB3GwAAAAESAQT1SR+/AgRyHP1DAwRAdxsAAAABGAEEbMEWvwIEx/H5QwMEQHcbAAQEgMuk"
    "AAAAARIBBLZgC78CBOS49UMDBEB3GwAAAAESAQTv7u6+AgRVVe9DAwRAdxsAAAABEgEEchzH"
    "vgIEx3HoQwMEQHcbAAAAARIBBJqZmb4CBACA4UMDBEB3GwAAAAESAQQC/83MAf9MvgIEAADa"
    "QwMEQHcbAAAAARIBBM3MzL0CBAAA00MDBEB3GwAAAAESAQSJiAi9AgQF/6sqzEMDBEB3GwAA"
    "AAESAQRhCza9AgTkOMZDAwRAdxsAAAABEgEE9UkfvgIEHMfAQwMEQHcbAAAAARIBBGELtr4C"
    "BBzHu0MDBEB3GwAAAAESAQTkOA6/AgQcR7dDAwRAdxsAAAABEgEE6ZM+vwIE5LizQwMEQHcb"
    "AAAAARIBBFuwhb8CBOQ4sUMDBEB3GwAAAAESAQQ5jqO/AgSO469DAwRAdxsAAAABEgEEjuO4"
    "vwIE5DivQwMEQHcbAAAAARIBBKVPur8CBBxHrgL/QwMEQAH/dxsAAAABEgEEpU+6vwIEHMet"
    "QwMEQHcbAAAAARIBBLy7u78CBFXVrUMDBEB3GwAAAAEF/xIBBKVPur8CBBzHrUMDBEB3GwAA"
    "AAEYAQS8u7u/AgRV1a1DAwRAdxsABASA7jYAAAABEgEEpU+6vwIEHMetQwMEQHcbAAAAARIB"
    "BHd3t78CBKsqrkMDBEB3GwAAAAESAQQGW7C/AgSO465DAwRAdxsAAAABEgEEZmamvwIEAICw"
    "QwMEQHcbAAAAARIBBJqZmb8CBAAAskMDBEB3GwAAAAESAQTNzIy/AgQAALVDAwRAdxsAAAAB"
    "EgEE0id9vwIEx3G4QwMEAv9AdxsAAAAB9wESAQSUPmm/AgQ5jr1DAwRAdxsAAAABEgEEMzMz"
    "vwIEAADEQwMEQHcbAAAAARIBBFuwBb8FtwIEchzMQwMEQHcbAAAAARIBBAZbML8CBMfx10MD"
    "BEB3GwAAAAESAQRyHEe/AgSOY+NDAwRAdxsAAAABEgEEsAVbvwIEHMfuQwMEQHcbAAAAARIB"
    "BLAFW78CBBxH+EMDBEB3GwAAAAESAQTv7m6/AgSrqv5DAwRAdxsAAAABEgEE3t1dvwIEVVX+"
    "QwMEQHcbAAAAARIBBBdsQb8CBBzH/UMDBIDGEwACAQoDDAEECgAAAAIEZAAAAAYCYOoIBMAn"
    "CQA="
)


def test_write_variable_uint_le() -> None:
    """Values are encoded in the smallest little-endian width."""
    assert write_variable_uint_le(2) == b"\x02"
    assert write_variable_uint_le(300) == b"\x2c\x01"
    assert write_variable_uint_le(70000) == b"\x70\x11\x01\x00"


def test_tlv_encode_splits_long_values() -> None:
    """A value longer than 255 bytes is split across repeated entries."""
    assert tlv_encode(0x01, b"\x02") == b"\x01\x01\x02"
    assert (
        tlv_encode(0x09, b"\xaa" * 256) == b"\x09\xff" + b"\xaa" * 255 + b"\x09\x01\xaa"
    )


def test_tlv_list_uses_the_empty_delimiter() -> None:
    """Repeated entries are separated by a zero length TLV, as HAP expects."""
    assert (
        tlv_encode_list(0x01, [b"\xaa", b"\xbb"]) == b"\x01\x01\xaa\x00\x00\x01\x01\xbb"
    )
    assert tlv_encode_list(0x01, []) == b"\x01\x00"


def test_tlv_decode_rejoins_split_values() -> None:
    """Decoding is the inverse of encoding for values of any length."""
    value = bytes(range(256)) * 2
    assert tlv_decode(tlv_encode(0x07, value)) == [(0x07, value)]


def test_supported_transition_configuration() -> None:
    """Brightness and colour temperature are advertised with their iids."""
    encoded = base64.b64decode(supported_transition_configuration(2, 4))
    assert encoded == bytes.fromhex("010601010202010100000106010104020102")


def test_parse_real_transition_control_write() -> None:
    """A schedule from the Home app is parsed into a usable curve."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)

    assert transition is not None
    assert len(transition.curve) == 42
    assert transition.update_interval == 60000
    assert transition.notify_threshold == 600000
    assert (transition.min_multiplier, transition.max_multiplier) == (10, 100)
    assert len(transition.transition_id) == 16


def test_interpolate_covers_a_full_day() -> None:
    """The schedule walks a full day of colour temperatures.

    The Home app may send points slightly outside the advertised range of the
    characteristic (it sent 509 mireds for a light advertising 500), which is
    why the controller clamps the interpolated value before writing it.
    """
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    start = transition.start_millis + transition.time_millis_offset

    values = []
    for minutes in range(0, 24 * 60, 37):
        value = interpolate(transition, start + minutes * 60000)
        if value is None:
            break
        assert 100 <= value <= 600
        values.append(value)

    assert len(values) > 30
    assert max(values) - min(values) > 100


def test_interpolate_returns_none_past_the_end() -> None:
    """The schedule only covers 24 hours; afterwards there is nothing to apply."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    start = transition.start_millis + transition.time_millis_offset
    assert interpolate(transition, start + 48 * 3600 * 1000) is None


def test_transition_survives_serialization() -> None:
    """A stored schedule is restored unchanged after a restart."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    assert _transition_from_dict(_transition_as_dict(transition)) == transition


def test_parse_rejects_an_empty_write() -> None:
    """Clearing the characteristic does not produce a transition."""
    assert parse_transition_control(base64.b64encode(b"").decode()) is None


async def _setup_light(hass: HomeAssistant, hk_driver, state: str = STATE_ON) -> Light:
    """Create a light accessory with adaptive lighting enabled."""
    entity_id = "light.demo"
    hass.states.async_set(
        entity_id,
        state,
        {
            ATTR_SUPPORTED_COLOR_MODES: ["color_temp"],
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4000,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, {CONF_ADAPTIVE_LIGHTING: True})
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()
    return acc


async def _write_control(hass: HomeAssistant, acc: Light, value: str) -> None:
    """Write the transition control characteristic as the Home app would."""
    assert acc.adaptive_lighting is not None
    acc.adaptive_lighting.char_control.client_update_value(value)
    await hass.async_block_till_done()


async def _wait_for_light_coalesce(hass: HomeAssistant) -> None:
    """Wait for the light characteristic writes to be coalesced into a call."""
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=CHANGE_COALESCE_TIME_WINDOW)
    )
    await hass.async_block_till_done()


async def test_the_accessory_advertises_adaptive_lighting(
    hass: HomeAssistant, hk_driver
) -> None:
    """A light configured for adaptive lighting exposes the three characteristics."""
    acc = await _setup_light(hass, hk_driver)

    assert acc.adaptive_lighting is not None
    controller = acc.adaptive_lighting
    assert controller.char_active_count.value == 0
    assert controller.char_supported.value
    assert base64.b64decode(controller.char_supported.value)


async def test_adaptive_lighting_is_off_without_the_option(
    hass: HomeAssistant, hk_driver
) -> None:
    """Without the option the light behaves exactly as before."""
    hass.states.async_set(
        "light.demo", STATE_ON, {ATTR_SUPPORTED_COLOR_MODES: ["color_temp"]}
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", "light.demo", 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    assert acc.adaptive_lighting is None


async def test_a_schedule_applies_a_colour_temperature(
    hass: HomeAssistant, hk_driver, hass_storage: dict[str, Any]
) -> None:
    """A schedule from the Home app drives the light on the next update."""
    acc = await _setup_light(hass, hk_driver)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.char_active_count.value == 1
    assert acc.adaptive_lighting.transition is not None
    assert len(call_turn_on) == 1
    assert ATTR_COLOR_TEMP_KELVIN in call_turn_on[0].data
    # The schedule is stored so it survives a restart.
    assert "light.demo" in hass_storage["homekit.adaptive_lighting"]["data"]


async def test_a_control_read_reports_the_running_transition(
    hass: HomeAssistant, hk_driver
) -> None:
    """Reading the control characteristic answers with the transition status."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)

    assert acc.adaptive_lighting is not None
    response = tlv_decode(base64.b64decode(acc.adaptive_lighting.char_control.value))
    assert response and response[0][0] == 0x01


async def test_a_manual_colour_change_stops_adaptive_lighting(
    hass: HomeAssistant, hk_driver
) -> None:
    """HomeKit expects a manual colour change to disarm adaptive lighting."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is not None

    acc._set_chars({CHAR_COLOR_TEMPERATURE: 300})
    await hass.async_block_till_done()

    assert acc.adaptive_lighting.transition is None
    assert acc.adaptive_lighting.char_active_count.value == 0
    assert acc.adaptive_lighting.char_control.value == ""


async def test_clearing_the_control_stops_adaptive_lighting(
    hass: HomeAssistant, hk_driver
) -> None:
    """The Home app disables adaptive lighting with an empty write."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)

    await _write_control(hass, acc, "")

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is None


async def test_a_write_without_a_configuration_stops_adaptive_lighting(
    hass: HomeAssistant, hk_driver
) -> None:
    """A write that carries no configuration disarms rather than raising."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)

    # Tag 0x01 is a read request, not an update.
    await _write_control(
        hass, acc, base64.b64encode(tlv_encode(0x01, b"\x00")).decode()
    )

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is None


async def test_an_unparsable_write_is_ignored(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed schedule is logged instead of breaking the accessory."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    truncated = tlv_encode(
        0x02,
        tlv_encode(
            0x01,
            tlv_encode(
                0x02,
                tlv_encode(0x01, b"\x01" * 16, 0x02, b"\x00\x00"),
                0x05,
                tlv_encode(0x01, b"\x00"),
            ),
        ),
    )
    await _write_control(hass, acc, base64.b64encode(truncated).decode())

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is None
    assert "could not parse the transition schedule" in caplog.text


async def test_the_light_is_not_switched_on_while_off(
    hass: HomeAssistant, hk_driver
) -> None:
    """A schedule never turns a light on by itself."""
    acc = await _setup_light(hass, hk_driver, state=STATE_OFF)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)

    assert not call_turn_on


async def test_a_schedule_written_to_the_service_does_not_switch_the_light_on(
    hass: HomeAssistant, hk_driver
) -> None:
    """The schedule reaches the light service setter as well, and means nothing there."""
    acc = await _setup_light(hass, hk_driver, state=STATE_OFF)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    # HAP hands a write to the characteristic setter and to the service setter
    # alike, so the transition control value arrives here too.
    acc._set_chars({CHAR_TRANSITION_CONTROL: TRANSITION_CONTROL_WRITE})
    await _wait_for_light_coalesce(hass)

    assert not call_turn_on
    assert not call_turn_off
    assert hass.states.get("light.demo").state == STATE_OFF


async def test_a_schedule_written_to_the_service_does_not_switch_the_light_off(
    hass: HomeAssistant, hk_driver
) -> None:
    """A schedule is not a request to switch a lit light off either."""
    acc = await _setup_light(hass, hk_driver, state=STATE_ON)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    acc._set_chars({CHAR_TRANSITION_CONTROL: TRANSITION_CONTROL_WRITE})
    await _wait_for_light_coalesce(hass)

    assert not call_turn_on
    assert not call_turn_off
    assert hass.states.get("light.demo").state == STATE_ON


async def test_the_same_value_is_not_sent_twice(
    hass: HomeAssistant, hk_driver, freezer: FrozenDateTimeFactory
) -> None:
    """Only a changed colour temperature reaches the light."""
    acc = await _setup_light(hass, hk_driver)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)
    assert len(call_turn_on) == 1

    # One update interval later the curve has barely moved.
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _wait_for_light_coalesce(hass)

    assert len(call_turn_on) == 1


async def test_the_end_of_the_curve_stops_adaptive_lighting(
    hass: HomeAssistant, hk_driver, freezer: FrozenDateTimeFactory
) -> None:
    """After 24 hours the schedule is spent and the Home app sends a new one."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)
    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is not None

    freezer.tick(timedelta(hours=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert acc.adaptive_lighting.transition is None


async def test_a_schedule_is_restored_after_a_restart(
    hass: HomeAssistant, hk_driver
) -> None:
    """The saved schedule is resumed without waiting for the Home app."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    assert acc.adaptive_lighting is not None
    stored = await _get_store(hass).async_get("light.demo")
    assert stored is not None

    # A restart builds a new accessory against the same store.
    hass.data.pop(DATA_STORE)
    restarted = Light(
        hass, hk_driver, "Light", "light.demo", 1, {CONF_ADAPTIVE_LIGHTING: True}
    )
    hk_driver.add_accessory(restarted)
    restarted.run()
    await hass.async_block_till_done()

    assert restarted.adaptive_lighting is not None
    assert restarted.adaptive_lighting.transition is not None
    assert restarted.adaptive_lighting.char_active_count.value == 1


async def test_an_expired_schedule_is_dropped_on_restart(
    hass: HomeAssistant, hk_driver
) -> None:
    """A schedule that no longer covers the current time is not resumed."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    expired = _transition_as_dict(transition)
    expired["time_millis_offset"] = int(time.time() * 1000)
    await _get_store(hass).async_set("light.demo", expired)

    acc = await _setup_light(hass, hk_driver)

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is None
    assert await _get_store(hass).async_get("light.demo") is None


async def test_an_unreadable_stored_schedule_is_dropped(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
    """A stored schedule from an older version does not break the accessory."""
    await _get_store(hass).async_set("light.demo", {"transition_id": "not a schedule"})

    acc = await _setup_light(hass, hk_driver)

    assert acc.adaptive_lighting is not None
    assert acc.adaptive_lighting.transition is None
    assert "stored transition is unreadable" in caplog.text
    assert await _get_store(hass).async_get("light.demo") is None


async def test_brightness_shifts_the_colour_temperature(
    hass: HomeAssistant, hk_driver
) -> None:
    """Apple dims a light towards warmer white with the adjustment factor."""
    acc = await _setup_light(hass, hk_driver)
    assert acc.adaptive_lighting is not None
    acc.adaptive_lighting.char_brightness.set_value(100)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)
    at_full = call_turn_on[0].data[ATTR_COLOR_TEMP_KELVIN]

    # Dimming re-applies the same curve point with a smaller multiplier.
    acc.adaptive_lighting.char_brightness.set_value(10)
    acc.adaptive_lighting._last_applied = None
    await acc.adaptive_lighting._async_update()
    await _wait_for_light_coalesce(hass)

    assert len(call_turn_on) == 2
    assert call_turn_on[1].data[ATTR_COLOR_TEMP_KELVIN] != at_full


async def test_switching_the_light_on_applies_the_curve_at_once(
    hass: HomeAssistant, hk_driver
) -> None:
    """A light coming on gets its colour now, not at the next update."""
    acc = await _setup_light(hass, hk_driver, state=STATE_OFF)
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    hass.states.async_set(
        "light.demo",
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: ["color_temp"],
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4000,
        },
    )
    await hass.async_block_till_done()
    await _wait_for_light_coalesce(hass)

    assert len(call_turn_on) == 1
    assert ATTR_COLOR_TEMP_KELVIN in call_turn_on[0].data


async def test_a_brightness_change_applies_the_curve_at_once(
    hass: HomeAssistant, hk_driver
) -> None:
    """Apple shifts the colour with brightness, so a new level is a new colour."""
    acc = await _setup_light(hass, hk_driver)
    assert acc.adaptive_lighting is not None
    acc.adaptive_lighting.char_brightness.set_value(100)
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    await _wait_for_light_coalesce(hass)
    assert len(call_turn_on) == 1
    at_full = call_turn_on[0].data[ATTR_COLOR_TEMP_KELVIN]

    # Dimming lands on another point of the curve, with no update in between.
    acc.adaptive_lighting.char_brightness.set_value(10)
    hass.states.async_set(
        "light.demo",
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: ["color_temp"],
            ATTR_BRIGHTNESS: 26,
            ATTR_COLOR_TEMP_KELVIN: 4000,
        },
    )
    await hass.async_block_till_done()
    await _wait_for_light_coalesce(hass)

    assert len(call_turn_on) == 2
    assert call_turn_on[1].data[ATTR_COLOR_TEMP_KELVIN] != at_full


def _control_write(configuration: bytes) -> str:
    """Wrap a configuration the way the Home app writes it."""
    return base64.b64encode(
        tlv_encode(TAG_UPDATE_TRANSITION, tlv_encode(TAG_CFG_IID, configuration))
    ).decode()


def test_write_variable_uint_le_rejects_impossible_values() -> None:
    """HAP has no encoding for a negative or larger than 32 bit value."""
    with pytest.raises(ValueError, match="negative"):
        write_variable_uint_le(-1)
    with pytest.raises(ValueError, match="32 bits"):
        write_variable_uint_le(2**32)


def test_tlv_encode_rejects_bad_arguments() -> None:
    """Tags and values are encoded in pairs of int and bytes."""
    with pytest.raises(ValueError, match="even number"):
        tlv_encode(0x01)
    with pytest.raises(TypeError, match="int tag"):
        tlv_encode(0x01, "not bytes")
    assert tlv_encode(0x01, b"") == b"\x01\x00"


def test_parse_rejects_incomplete_schedules() -> None:
    """A write that is not a complete schedule leaves the light alone."""
    curve = tlv_encode(
        TAG_CURVE_ENTRY,
        tlv_encode(
            TAG_ENTRY_ADJUSTMENT_FACTOR,
            b"\x00\x00\x00\x00",
            TAG_ENTRY_VALUE,
            b"\x00\x00\x7a\x43",
        ),
    )
    parameters = tlv_encode(
        TAG_PARAM_TRANSITION_ID, b"\x01" * 16, TAG_PARAM_START_TIME, b"\x00" * 8
    )

    # A read request carries no update at all.
    assert (
        parse_transition_control(base64.b64encode(tlv_encode(0x01, b"\x00")).decode())
        is None
    )
    # An update without the parameters and the curve.
    assert (
        parse_transition_control(_control_write(tlv_encode(TAG_CFG_IID, b"\x0b")))
        is None
    )
    # Parameters without the start time.
    assert (
        parse_transition_control(
            _control_write(
                tlv_encode(
                    TAG_CFG_PARAMETERS,
                    tlv_encode(TAG_PARAM_TRANSITION_ID, b"\x01" * 16),
                    TAG_CFG_CURVE,
                    curve,
                )
            )
        )
        is None
    )
    # A curve needs two points to interpolate between.
    assert (
        parse_transition_control(
            _control_write(
                tlv_encode(TAG_CFG_PARAMETERS, parameters, TAG_CFG_CURVE, curve)
            )
        )
        is None
    )


async def test_a_new_schedule_replaces_the_running_one(
    hass: HomeAssistant, hk_driver
) -> None:
    """The Home app renews the schedule roughly daily."""
    acc = await _setup_light(hass, hk_driver)
    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)
    assert acc.adaptive_lighting is not None
    first = acc.adaptive_lighting.transition

    await _write_control(hass, acc, TRANSITION_CONTROL_WRITE)

    assert acc.adaptive_lighting.transition is not first
    assert acc.adaptive_lighting.char_active_count.value == 1


async def test_the_controller_does_nothing_while_disarmed(
    hass: HomeAssistant, hk_driver
) -> None:
    """Without a schedule there is nothing to answer, apply or stop."""
    acc = await _setup_light(hass, hk_driver)
    controller = acc.adaptive_lighting
    assert controller is not None

    assert controller._build_control_response() == ""
    await controller._async_update()
    controller.notify_manual_change()

    assert controller.transition is None
    assert controller.char_active_count.value == 0


async def test_no_curve_point_applies_past_the_end(
    hass: HomeAssistant, hk_driver
) -> None:
    """The brightness factor is only known inside the 24 hours of the curve."""
    acc = await _setup_light(hass, hk_driver)
    assert acc.adaptive_lighting is not None
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    transition.time_millis_offset -= 48 * 3600 * 1000

    assert acc.adaptive_lighting._current_curve_point(transition) is None


def test_an_incomplete_curve_entry_is_skipped() -> None:
    """A point that carries no value is dropped, the rest of the curve stands."""
    point = tlv_encode(
        TAG_ENTRY_ADJUSTMENT_FACTOR,
        b"\x00\x00\x00\x00",
        TAG_ENTRY_VALUE,
        b"\x00\x00\x7a\x43",
    )
    schedule = _control_write(
        tlv_encode(
            TAG_CFG_PARAMETERS,
            tlv_encode(
                TAG_PARAM_TRANSITION_ID, b"\x01" * 16, TAG_PARAM_START_TIME, b"\x00" * 8
            ),
            TAG_CFG_CURVE,
            tlv_encode_list(
                TAG_CURVE_ENTRY,
                [
                    point,
                    tlv_encode(TAG_ENTRY_ADJUSTMENT_FACTOR, b"\x00\x00\x00\x00"),
                    point,
                ],
            ),
        )
    )

    transition = parse_transition_control(schedule)

    assert transition is not None
    assert len(transition.curve) == 2
