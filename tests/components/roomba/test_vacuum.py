"""Tests for the Roomba vacuum platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_SET_FAN_SPEED,
    VacuumActivity,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

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
    mock_roomba.master_state["state"]["reported"]["detectedPad"] = "reusableWet"

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

    mock_roomba.set_preference.assert_any_call("carpetBoost", "False")
    mock_roomba.set_preference.assert_any_call("vacHigh", "False")
