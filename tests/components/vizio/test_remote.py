"""Tests for Vizio remote platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import MOCK_SPEAKER_CONFIG, MOCK_USER_VALID_TV_CONFIG, NAME, UNIQUE_ID

from tests.common import MockConfigEntry

REMOTE_ENTITY_ID = f"{REMOTE_DOMAIN}.{slugify(NAME)}"


async def _setup_entry(
    hass: HomeAssistant, config: dict, unique_id: str = UNIQUE_ID
) -> MockConfigEntry:
    """Set up a Vizio config entry and return it."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=config, unique_id=unique_id)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.mark.parametrize(
    "config",
    [MOCK_USER_VALID_TV_CONFIG, MOCK_SPEAKER_CONFIG],
    ids=["tv", "speaker"],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_remote_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config: dict,
) -> None:
    """Test remote entity is created for TV and speaker."""
    await _setup_entry(hass, config)
    state = hass.states.get(REMOTE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    entry = entity_registry.async_get(REMOTE_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == UNIQUE_ID


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_remote_is_off_when_device_off(hass: HomeAssistant) -> None:
    """Test remote state is off when device is off."""
    with patch(
        "homeassistant.components.vizio.VizioAsync.get_power_state",
        return_value=False,
    ):
        await _setup_entry(hass, MOCK_SPEAKER_CONFIG)
        state = hass.states.get(REMOTE_ENTITY_ID)
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_TURN_ON, "pow_on"),
        (SERVICE_TURN_OFF, "pow_off"),
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_turn_on_off(hass: HomeAssistant, service: str, mock_method: str) -> None:
    """Test turning on/off the remote sends the correct power command."""
    await _setup_entry(hass, MOCK_SPEAKER_CONFIG)
    with patch(
        f"homeassistant.components.vizio.VizioAsync.{mock_method}",
    ) as mock_power:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: REMOTE_ENTITY_ID},
            blocking=True,
        )
        mock_power.assert_called_once_with(log_api_exception=False)


@pytest.mark.parametrize(
    ("command", "expected_key"),
    [
        # Native keys (lowercase tested for a few to verify case-insensitivity)
        ("BACK", "BACK"),
        ("CC_TOGGLE", "CC_TOGGLE"),
        ("ch_up", "CH_UP"),
        ("menu", "MENU"),
        ("SMARTCAST", "SMARTCAST"),
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_tv_valid(
    hass: HomeAssistant, command: str, expected_key: str
) -> None:
    """Test send_command resolves valid TV commands."""
    await _setup_entry(hass, MOCK_USER_VALID_TV_CONFIG)
    with patch(
        "homeassistant.components.vizio.VizioAsync.remote",
    ) as mock_remote:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: [command],
            },
            blocking=True,
        )
        mock_remote.assert_called_once_with(expected_key, log_api_exception=False)


@pytest.mark.parametrize("command", ["INVALID_KEY", "not_a_key"])
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_tv_invalid(hass: HomeAssistant, command: str) -> None:
    """Test send_command raises error for invalid TV commands."""
    await _setup_entry(hass, MOCK_USER_VALID_TV_CONFIG)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: [command],
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("command", "expected_key"),
    [
        # Native keys (lowercase tested for a couple)
        ("MUTE_OFF", "MUTE_OFF"),
        ("MUTE_ON", "MUTE_ON"),
        ("MUTE_TOGGLE", "MUTE_TOGGLE"),
        ("pause", "PAUSE"),
        ("PLAY", "PLAY"),
        ("POW_OFF", "POW_OFF"),
        ("POW_ON", "POW_ON"),
        ("POW_TOGGLE", "POW_TOGGLE"),
        ("vol_down", "VOL_DOWN"),
        ("VOL_UP", "VOL_UP"),
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_speaker_valid(
    hass: HomeAssistant, command: str, expected_key: str
) -> None:
    """Test send_command resolves valid speaker commands."""
    await _setup_entry(hass, MOCK_SPEAKER_CONFIG)
    with patch(
        "homeassistant.components.vizio.VizioAsync.remote",
    ) as mock_remote:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: [command],
            },
            blocking=True,
        )
        mock_remote.assert_called_once_with(expected_key, log_api_exception=False)


@pytest.mark.parametrize(
    "command",
    [
        # TV-only native keys
        "MENU",
        "CH_UP",
        "INPUT_NEXT",
        # Completely invalid
        "INVALID_KEY",
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_speaker_invalid(hass: HomeAssistant, command: str) -> None:
    """Test speaker remote rejects TV-only and invalid keys."""
    await _setup_entry(hass, MOCK_SPEAKER_CONFIG)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: [command],
            },
            blocking=True,
        )


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_multiple(hass: HomeAssistant) -> None:
    """Test send_command with multiple commands in one call."""
    await _setup_entry(hass, MOCK_USER_VALID_TV_CONFIG)
    with patch(
        "homeassistant.components.vizio.VizioAsync.remote",
    ) as mock_remote:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["UP", "OK"],
            },
            blocking=True,
        )
        assert mock_remote.call_count == 2
        mock_remote.assert_any_call("UP", log_api_exception=False)
        mock_remote.assert_any_call("OK", log_api_exception=False)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_invalid_skips_valid(hass: HomeAssistant) -> None:
    """Test that no commands are sent when one command in the list is invalid."""
    await _setup_entry(hass, MOCK_USER_VALID_TV_CONFIG)
    with (
        patch(
            "homeassistant.components.vizio.VizioAsync.remote",
        ) as mock_remote,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["UP", "INVALID_KEY"],
            },
            blocking=True,
        )
    mock_remote.assert_not_called()


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_delay_between_repeats(hass: HomeAssistant) -> None:
    """Test delay is applied between repeats but not after the last one."""
    await _setup_entry(hass, MOCK_USER_VALID_TV_CONFIG)
    with (
        patch(
            "homeassistant.components.vizio.VizioAsync.remote",
        ) as mock_remote,
        patch(
            "homeassistant.components.vizio.remote.asyncio.sleep",
        ) as mock_sleep,
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["UP"],
                ATTR_NUM_REPEATS: 3,
                ATTR_DELAY_SECS: 0.5,
            },
            blocking=True,
        )
        assert mock_remote.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.5)
