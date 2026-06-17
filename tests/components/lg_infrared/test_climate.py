"""Tests for the LG Infrared climate platform."""

from collections.abc import Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.lg_infrared import ac_encoder
from homeassistant.components.lg_infrared.climate import LgAcClimateEntity
from homeassistant.components.lg_infrared.const import MIN_TEMP
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE_ENTITY_ID = "climate.lg_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


# ── Setup / snapshot ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("init_ac_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_ac_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_ac_config_entry.entry_id
    )


@pytest.mark.usefixtures("init_ac_integration")
async def test_availability_follows_emitter(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test climate entity availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, EMITTER_ENTITY_ID
    )


# ── HVAC mode ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("init_ac_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test setting HVAC mode to off sends power-off timings."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == ac_encoder.encode_off()


@pytest.mark.usefixtures("init_ac_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "temp", "fan", "expected_timings_fn"),
    [
        pytest.param(
            HVACMode.COOL,
            24,
            FAN_AUTO,
            lambda: ac_encoder.encode_cool(24, FAN_AUTO),
            id="cool_24_auto",
        ),
        pytest.param(
            HVACMode.COOL,
            18,
            FAN_LOW,
            lambda: ac_encoder.encode_cool(18, FAN_LOW),
            id="cool_18_low",
        ),
        pytest.param(
            HVACMode.COOL,
            30,
            FAN_HIGH,
            lambda: ac_encoder.encode_cool(30, FAN_HIGH),
            id="cool_30_high",
        ),
        pytest.param(
            HVACMode.DRY,
            24,
            FAN_MEDIUM,
            lambda: ac_encoder.encode_dry(FAN_MEDIUM),
            id="dry_auto",
        ),
    ],
)
async def test_set_hvac_mode_encodes_correctly(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    temp: int,
    fan: str,
    expected_timings_fn: Callable[[], list[int]],
) -> None:
    """Test that set_hvac_mode sends correctly encoded timings."""
    # Set initial temperature and fan before switching mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: temp},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": fan},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_timings_fn()


@pytest.mark.usefixtures("init_ac_integration_all_modes")
@pytest.mark.parametrize(
    ("hvac_mode", "expected_timings_fn"),
    [
        pytest.param(
            HVACMode.HEAT,
            lambda: ac_encoder.encode_heat(MIN_TEMP, FAN_AUTO),
            id="heat",
        ),
        pytest.param(
            HVACMode.FAN_ONLY,
            lambda: ac_encoder.encode_fan_only(FAN_AUTO),
            id="fan_only",
        ),
    ],
)
async def test_set_hvac_mode_heat_and_fan_only(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    expected_timings_fn: Callable[[], list[int]],
) -> None:
    """Test heat and fan-only modes encode from the entity defaults."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_timings_fn()


def test_encode_mode_rejects_unsupported_mode(
    mock_ac_config_entry: MockConfigEntry,
) -> None:
    """Test _encode_mode raises for a mode outside the supported set."""
    entity = LgAcClimateEntity(mock_ac_config_entry, EMITTER_ENTITY_ID)
    with pytest.raises(HomeAssistantError):
        entity._encode_mode(HVACMode.AUTO, MIN_TEMP, FAN_AUTO)


# ── Temperature ───────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("init_ac_integration")
async def test_set_temperature_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature sends IR when AC is on."""
    # Turn on first
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 26},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == ac_encoder.encode_cool(26, FAN_AUTO)

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 26.0


@pytest.mark.usefixtures("init_ac_integration")
async def test_set_temperature_no_command_when_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature updates state but sends no IR when AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 22.0


@pytest.mark.usefixtures("init_ac_integration")
async def test_set_temperature_no_command_in_dry_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature sends no IR in dry mode (protocol-fixed temp)."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0


# ── Fan mode ──────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("init_ac_integration")
async def test_set_fan_mode_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_fan_mode sends IR when AC is on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_HIGH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == ac_encoder.encode_cool(MIN_TEMP, FAN_HIGH)


# ── Receiver state updates ────────────────────────────────────────────────────


@pytest.mark.usefixtures("init_ac_integration_with_receiver")
async def test_receiver_updates_state_on_cool_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that a received cool signal updates the climate entity state."""
    timings = ac_encoder.encode_cool(24, FAN_MEDIUM)

    signal = InfraredReceivedSignal(timings=timings)
    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes["fan_mode"] == FAN_MEDIUM
    assert float(state.attributes["temperature"]) == 24.0


@pytest.mark.usefixtures("init_ac_integration_with_receiver")
async def test_receiver_updates_state_on_off_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that a received off signal sets mode to off."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=ac_encoder.encode_off())
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("init_ac_integration_with_receiver")
async def test_receiver_ignores_non_lg_ac_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that an unrecognised IR signal does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[500, -500, 300, -300])
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF  # unchanged from initial


async def test_receiver_subscribe_failure_warns_and_continues(
    hass: HomeAssistant,
    mock_ac_config_entry_with_receiver: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    platforms: list[Platform],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the entity still sets up and warns if receiver subscription fails."""
    mock_ac_config_entry_with_receiver.add_to_hass(hass)
    with (
        patch("homeassistant.components.lg_infrared.PLATFORMS", platforms),
        patch(
            "homeassistant.components.lg_infrared.climate.async_subscribe_receiver",
            side_effect=HomeAssistantError("boom"),
        ),
    ):
        await hass.config_entries.async_setup(
            mock_ac_config_entry_with_receiver.entry_id
        )
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert "physical remote state updates will be unavailable" in caplog.text


# ── Encoder unit tests ────────────────────────────────────────────────────────


def test_encode_off_frame() -> None:
    """encode_off must produce frame 0x88C0051 (verified against captures)."""
    timings = ac_encoder.encode_off()
    # header is LG2-short: 3200/9900
    assert timings[0] == ac_encoder._OFF_HDR_MARK
    assert abs(timings[1]) == ac_encoder._OFF_HDR_SPACE
    # decode and verify frame value
    frame = _extract_frame(timings)
    assert frame == 0x88C0051


def test_encode_cool_24_auto_frame() -> None:
    """encode_cool(24,'auto') must produce frame 0x880095E (verified against captures)."""
    timings = ac_encoder.encode_cool(24, FAN_AUTO)
    assert timings[0] == ac_encoder._HDR_MARK
    frame = _extract_frame(timings)
    assert frame == 0x880095E


def test_encode_dry_auto_frame() -> None:
    """encode_dry('auto') must produce frame 0x880195F (verified against captures)."""
    timings = ac_encoder.encode_dry(FAN_AUTO)
    frame = _extract_frame(timings)
    assert frame == 0x880195F


@pytest.mark.parametrize(
    ("temp", "fan", "expected_hex"),
    [
        pytest.param(18, FAN_AUTO, 0x8800358, id="18_auto"),
        pytest.param(30, FAN_AUTO, 0x8800F54, id="30_auto"),
        pytest.param(24, FAN_LOW, 0x8800909, id="24_low"),
        pytest.param(24, FAN_MEDIUM, 0x880092B, id="24_medium"),
        pytest.param(24, FAN_HIGH, 0x880094D, id="24_high"),
    ],
)
def test_encode_cool_frames(temp: int, fan: str, expected_hex: int) -> None:
    """Verify cool encoder against known-good frames."""
    timings = ac_encoder.encode_cool(temp, fan)
    frame = _extract_frame(timings)
    assert frame == expected_hex


def test_decode_roundtrip_cool() -> None:
    """Decoded cool frame must reconstruct original mode/fan/temp."""
    timings = ac_encoder.encode_cool(22, FAN_HIGH)
    result = ac_encoder.decode_timings(timings)
    assert result is not None
    assert result["mode"] == HVACMode.COOL
    assert result["fan"] == FAN_HIGH
    assert result["temp_c"] == 22


def test_decode_roundtrip_off() -> None:
    """Decoded off frame must return HVACMode.OFF."""
    result = ac_encoder.decode_timings(ac_encoder.encode_off())
    assert result is not None
    assert result["mode"] == HVACMode.OFF


def test_decode_roundtrip_dry() -> None:
    """Decoded dry frame must return HVACMode.DRY."""
    result = ac_encoder.decode_timings(ac_encoder.encode_dry(FAN_LOW))
    assert result is not None
    assert result["mode"] == HVACMode.DRY
    assert result["fan"] == FAN_LOW


def test_decode_roundtrip_heat() -> None:
    """Decoded heat frame must reconstruct original mode/fan/temp."""
    result = ac_encoder.decode_timings(ac_encoder.encode_heat(26, FAN_MEDIUM))
    assert result is not None
    assert result["mode"] == HVACMode.HEAT
    assert result["fan"] == FAN_MEDIUM
    assert result["temp_c"] == 26


def test_decode_roundtrip_fan_only() -> None:
    """Decoded fan-only frame must return HVACMode.FAN_ONLY."""
    result = ac_encoder.decode_timings(ac_encoder.encode_fan_only(FAN_HIGH))
    assert result is not None
    assert result["mode"] == HVACMode.FAN_ONLY
    assert result["fan"] == FAN_HIGH


def test_decode_returns_none_for_short_timings() -> None:
    """decode_timings must return None for incomplete signals."""
    assert ac_encoder.decode_timings([500, -400]) is None


def test_decode_returns_none_for_non_lg_ac() -> None:
    """decode_timings must return None for non-LG-AC frames."""
    # NEC-style header (9000/4500) with wrong signature
    junk = [9000, -4500] + [550, -1600] * 32
    assert ac_encoder.decode_timings(junk) is None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_frame(timings: list[int]) -> int:
    """Extract the 28-bit frame integer from raw timings."""
    frame = 0
    i = 2
    bits_read = 0
    while i + 1 < len(timings) and bits_read < 28:
        frame = (frame << 1) | (1 if abs(timings[i + 1]) > 1000 else 0)
        i += 2
        bits_read += 1
    return frame
