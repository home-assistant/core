"""Test the OpenGarage covers."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    CoverState,
)
from homeassistant.components.opengarage.const import CONF_DEVICE_KEY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "cover.garage_abcdef"


async def _setup_opengarage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the OpenGarage integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("door_state", "expected_state"),
    [
        pytest.param(0, CoverState.CLOSED, id="closed"),
        pytest.param(1, CoverState.OPEN, id="open"),
        pytest.param(2, CoverState.OPEN, id="stopped"),
        pytest.param(3, CoverState.CLOSING, id="closing"),
        pytest.param(4, CoverState.OPENING, id="opening"),
        pytest.param(5, STATE_UNKNOWN, id="unknown"),
        pytest.param(99, STATE_UNKNOWN, id="unsupported"),
    ],
)
async def test_cover_door_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
    door_state: int,
    expected_state: CoverState | str,
) -> None:
    """Test OpenGarage door state mapping."""
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": door_state,
    }

    await _setup_opengarage(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state


async def test_open_cover_uses_explicit_open_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """Test opening the cover uses the explicit open command."""
    device_key = "abc123&=?/"
    object.__setattr__(
        mock_config_entry,
        "data",
        {**mock_config_entry.data, CONF_DEVICE_KEY: device_key},
    )
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": 0,
    }
    mock_opengarage._execute.return_value = {"result": 1}

    await _setup_opengarage(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_opengarage._execute.assert_awaited_once_with(
        "cc?dkey=abc123%26%3D%3F%2F&open=1"
    )
    mock_opengarage.push_button.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.OPENING


async def test_close_cover_uses_explicit_close_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """Test closing the cover uses the explicit close command."""
    device_key = "abc123&=?/"
    object.__setattr__(
        mock_config_entry,
        "data",
        {**mock_config_entry.data, CONF_DEVICE_KEY: device_key},
    )
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": 1,
    }
    mock_opengarage._execute.return_value = {"result": 1}

    await _setup_opengarage(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_opengarage._execute.assert_awaited_once_with(
        "cc?dkey=abc123%26%3D%3F%2F&close=1"
    )
    mock_opengarage.push_button.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSING


async def test_cover_failed_command_reverts_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """Test a failed command reverts the optimistic state."""
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": 0,
    }
    mock_opengarage._execute.return_value = None

    await _setup_opengarage(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED


@pytest.mark.parametrize("result", [2, 99, "bad"])
async def test_cover_command_error_result_reverts_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
    result: int | str,
) -> None:
    """Test error result responses revert the optimistic state."""
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": 0,
    }
    mock_opengarage._execute.return_value = {"result": result}

    await _setup_opengarage(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED


@pytest.mark.parametrize(
    "data",
    [None, "bad", {"result": 2}, {"result": 99}, {"result": "bad"}],
)
async def test_close_cover_command_error_reverts_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
    data: dict[str, int | str] | str | None,
) -> None:
    """Test close command error responses revert the optimistic state."""
    mock_opengarage.update_state.return_value = {
        "name": "abcdef",
        "mac": "aa:bb:cc:dd:ee:ff",
        "fwv": "1.2.4",
        "door": 1,
    }
    mock_opengarage._execute.return_value = data

    await _setup_opengarage(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
