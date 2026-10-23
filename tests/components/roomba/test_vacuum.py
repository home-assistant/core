"""Tests for the Roomba vacuum platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from roombapy import RoombaConnectionError, RoombaScopeError

from homeassistant.components.vacuum import (
    ATTR_COMMAND,
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

ENTITY_ID = "vacuum.test_roomba"


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the vacuum platform only."""
    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.VACUUM]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("phase", "cycle", "expected"),
    [
        ("charge", "none", VacuumActivity.DOCKED),
        # Docked to recharge in the middle of a mission stays docked instead of
        # being reported as paused (regression test for #148287).
        ("charge", "clean", VacuumActivity.DOCKED),
        ("hmMidMsn", "clean", VacuumActivity.CLEANING),
        ("hmPostMsn", "clean", VacuumActivity.RETURNING),
        ("run", "clean", VacuumActivity.CLEANING),
        ("pause", "clean", VacuumActivity.PAUSED),
        # Stopped on the floor mid-mission is a paused state.
        ("stop", "clean", VacuumActivity.PAUSED),
        ("stop", "none", VacuumActivity.IDLE),
        ("stuck", "clean", VacuumActivity.ERROR),
    ],
)
async def test_vacuum_activity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    phase: str,
    cycle: str,
    expected: VacuumActivity,
) -> None:
    """Test the vacuum activity mapping from the reported mission status."""
    mock_roomba.master_state["state"]["reported"]["cleanMissionStatus"] = {
        "cycle": cycle,
        "phase": phase,
    }

    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.VACUUM]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("extra_state", "expect_fan_speed_support", "expected_fan_speed"),
    [
        # 67 is OVERLAP_STANDARD.
        ({"rankOverlap": 67}, True, "Standard-1"),
        # Combo models report a mop pad but no rankOverlap.
        ({}, False, None),
    ],
)
async def test_braava_fan_speed_requires_rank_overlap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    extra_state: dict[str, Any],
    expect_fan_speed_support: bool,
    expected_fan_speed: str | None,
) -> None:
    """Test that fan speed is only offered when it can be produced."""
    reported = mock_roomba.master_state["state"]["reported"]
    reported["detectedPad"] = "reusableWet"
    # fan_speed reads the "disposable" key.
    reported["padWetness"] = {"disposable": 1, "reusable": 1}
    reported.pop("rankOverlap", None)
    reported.update(extra_state)

    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.VACUUM]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    supported = VacuumEntityFeature(state.attributes["supported_features"])
    assert bool(supported & VacuumEntityFeature.FAN_SPEED) is expect_fan_speed_support
    assert state.attributes.get("fan_speed") == expected_fan_speed


@pytest.mark.parametrize(
    ("fan_speed", "translation_key"),
    [
        # Missing the "-<spray amount>" half entirely.
        ("Standard", "invalid_fan_speed_format"),
        # Spray amount present but not a number.
        ("Standard-x", "spray_amount_not_a_number"),
        # Well-formed, but the behavior is not one we support.
        ("Bogus-1", "invalid_mop_behavior"),
        # Well-formed, but the spray amount is out of range.
        ("Standard-9", "invalid_spray_amount"),
    ],
)
async def test_braava_set_fan_speed_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    fan_speed: str,
    translation_key: str,
) -> None:
    """Test that invalid Braava fan speeds raise instead of being swallowed."""
    reported = mock_roomba.master_state["state"]["reported"]
    reported["detectedPad"] = "reusableWet"
    # 67 is OVERLAP_STANDARD; without it the mop behavior is not offered at all.
    reported["rankOverlap"] = 67

    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: fan_speed},
            blocking=True,
        )

    assert err.value.translation_domain == "roomba"
    assert err.value.translation_key == translation_key


async def test_carpet_boost_set_fan_speed_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that an unknown carpet-boost fan speed raises instead of being swallowed."""
    mock_roomba.master_state["state"]["reported"]["cap"]["carpetBoost"] = 1

    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: "Turbo"},
            blocking=True,
        )

    assert err.value.translation_domain == "roomba"
    assert err.value.translation_key == "invalid_fan_speed"


async def test_carpet_boost_set_fan_speed_valid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that a valid fan speed still sets the preferences."""
    mock_roomba.master_state["state"]["reported"]["cap"]["carpetBoost"] = 1

    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: "eco"},
        blocking=True,
    )

    mock_roomba.set_preference.assert_any_await("carpetBoost", "False")
    mock_roomba.set_preference.assert_any_await("vacHigh", "False")


async def test_braava_set_fan_speed_valid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that a valid Braava fan speed sets the mop preferences."""
    reported = mock_roomba.master_state["state"]["reported"]
    reported["detectedPad"] = "reusableWet"
    reported["rankOverlap"] = 67

    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: "deep-2"},
        blocking=True,
    )

    # 85 is OVERLAP_DEEP.
    mock_roomba.set_preference.assert_any_await("rankOverlap", 85)
    mock_roomba.set_preference.assert_any_await(
        "padWetness", {"disposable": 2, "reusable": 2}
    )


@pytest.mark.parametrize(
    ("phase", "service", "service_data", "expected_args"),
    [
        pytest.param("charge", SERVICE_START, {}, ("start", None), id="start"),
        pytest.param("pause", SERVICE_START, {}, ("resume", None), id="resume"),
        pytest.param("run", SERVICE_STOP, {}, ("stop", None), id="stop"),
        pytest.param("run", SERVICE_PAUSE, {}, ("pause", None), id="pause"),
        pytest.param("stop", SERVICE_RETURN_TO_BASE, {}, ("dock", None), id="dock"),
        pytest.param("charge", SERVICE_LOCATE, {}, ("find", None), id="locate"),
        pytest.param(
            "charge",
            SERVICE_SEND_COMMAND,
            {ATTR_COMMAND: "evac", ATTR_PARAMS: {"key": "value"}},
            ("evac", {"key": "value"}),
            id="send_command",
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    phase: str,
    service: str,
    service_data: dict[str, Any],
    expected_args: tuple[Any, ...],
) -> None:
    """Test that vacuum actions are awaited on the client."""
    mock_roomba.master_state["state"]["reported"]["cleanMissionStatus"] = {
        "cycle": "clean",
        "phase": phase,
    }

    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_roomba.send_command.assert_awaited_once_with(*expected_args)


async def test_state_update_from_robot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that a message from the robot updates the entity state."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == VacuumActivity.DOCKED

    reported = mock_roomba.master_state["state"]["reported"]
    reported["cleanMissionStatus"] = {"cycle": "clean", "phase": "run"}
    on_message = mock_roomba.register_on_message_callback.call_args_list[-1].args[0]
    on_message({"state": {"reported": {"cleanMissionStatus": {"phase": "run"}}}})

    assert hass.states.get(ENTITY_ID).state == VacuumActivity.CLEANING


@pytest.mark.parametrize(
    ("service", "service_data", "method"),
    [
        pytest.param(SERVICE_LOCATE, {}, "send_command", id="command"),
        pytest.param(
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "eco"},
            "set_preference",
            id="preference",
        ),
    ],
)
async def test_action_while_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    method: str,
) -> None:
    """Test that an action fails with a clear error while the robot is offline."""
    mock_roomba.master_state["state"]["reported"]["cap"]["carpetBoost"] = 1
    getattr(mock_roomba, method).side_effect = RoombaConnectionError

    await _setup(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )

    assert err.value.translation_key == "not_connected"


async def test_send_command_with_empty_regions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that a room command without rooms is rejected, not run house-wide."""
    mock_roomba.send_command.side_effect = RoombaScopeError

    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_COMMAND: "start",
                ATTR_PARAMS: {"regions": []},
            },
            blocking=True,
        )

    assert err.value.translation_key == "empty_regions"
