"""Tests for the Philips TV remote."""

from unittest.mock import _Call, call

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

REMOTE_ENTITY_ID = "remote.philips_tv_remote"


async def setup_remote(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration with the mocked TV."""
    mock_tv.json_feature_supported.return_value = False
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("on", "powerstate", "screenstate", "expected_state"),
    [
        pytest.param(True, "On", None, STATE_ON, id="powerstate-on"),
        pytest.param(True, "On", "Off", STATE_ON, id="powerstate-on-screen-off"),
        pytest.param(True, "Standby", None, STATE_OFF, id="powerstate-standby"),
        pytest.param(True, "StandbyKeep", None, STATE_OFF, id="powerstate-standbykeep"),
        pytest.param(True, None, None, STATE_ON, id="no-powerstate-reachable"),
        pytest.param(True, None, "On", STATE_ON, id="no-powerstate-screen-on"),
        pytest.param(True, None, "Off", STATE_OFF, id="no-powerstate-screen-off"),
        pytest.param(False, None, None, STATE_OFF, id="unreachable"),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    on: bool,
    powerstate: str | None,
    screenstate: str | None,
    expected_state: str,
) -> None:
    """Test the remote state matches the media player's on/off rule."""
    mock_tv.on = on
    mock_tv.powerstate = powerstate
    mock_tv.screenstate = screenstate

    await setup_remote(hass, mock_tv, mock_config_entry)

    assert (state := hass.states.get(REMOTE_ENTITY_ID))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("on", "powerstate", "screenstate", "set_power_state_calls", "send_key_calls"),
    [
        pytest.param(
            True,
            "On",
            None,
            [call("Standby")],
            [],
            id="powerstate-uses-set-power-state",
        ),
        pytest.param(
            True,
            None,
            None,
            [],
            [call("Standby")],
            id="no-powerstate-falls-back-to-key",
        ),
        pytest.param(
            True, None, "On", [], [call("Standby")], id="no-powerstate-screen-on"
        ),
        pytest.param(
            True, "Standby", None, [], [], id="already-in-standby-sends-nothing"
        ),
        pytest.param(
            True, None, "Off", [], [], id="no-powerstate-screen-off-sends-nothing"
        ),
        pytest.param(False, None, None, [], [], id="unreachable-sends-nothing"),
    ],
)
async def test_turn_off(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    on: bool,
    powerstate: str | None,
    screenstate: str | None,
    set_power_state_calls: list[_Call],
    send_key_calls: list[_Call],
) -> None:
    """Test turning off.

    A TV in network standby still answers the API, so `on` is True while
    `powerstate` is "Standby" (or, without powerstate, `screenstate` is
    "Off"). The Standby key is a power toggle, so nothing may be sent then.
    """
    mock_tv.on = on
    mock_tv.powerstate = powerstate
    mock_tv.screenstate = screenstate

    await setup_remote(hass, mock_tv, mock_config_entry)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: REMOTE_ENTITY_ID},
        blocking=True,
    )

    assert mock_tv.setPowerState.mock_calls == set_power_state_calls
    assert mock_tv.sendKey.mock_calls == send_key_calls


async def test_turn_on_with_powerstate(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on a reachable TV that supports powerstate."""
    mock_tv.on = True
    mock_tv.powerstate = "Standby"

    await setup_remote(hass, mock_tv, mock_config_entry)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: REMOTE_ENTITY_ID},
        blocking=True,
    )

    mock_tv.setPowerState.assert_called_once_with("On")
