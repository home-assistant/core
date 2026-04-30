"""Tests for Vizio remote platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .conftest import setup_integration
from .const import NAME

from tests.common import MockConfigEntry, snapshot_platform

REMOTE_ENTITY_ID = f"{REMOTE_DOMAIN}.{slugify(NAME)}"


@pytest.fixture(autouse=True)
def remote_only() -> Generator[None]:
    """Only set up the remote platform."""
    with patch(
        "homeassistant.components.vizio.PLATFORMS",
        [Platform.REMOTE],
    ):
        yield


@pytest.mark.parametrize(
    "config_entry_fixture",
    ["mock_tv_config_entry", "mock_speaker_config_entry"],
    ids=["tv", "speaker"],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_remote_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test remote entity is created for TV and speaker."""
    config_entry: MockConfigEntry = request.getfixturevalue(config_entry_fixture)
    await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_remote_is_off_when_device_off(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test remote state is off when device is off."""
    with patch(
        "homeassistant.components.vizio.VizioAsync.get_power_state",
        return_value=False,
    ):
        await setup_integration(hass, mock_speaker_config_entry)
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
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_speaker_config_entry: MockConfigEntry,
    service: str,
    mock_method: str,
) -> None:
    """Test turning on/off the remote sends the correct power command."""
    await setup_integration(hass, mock_speaker_config_entry)
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
        ("BACK", "BACK"),
        ("ch_up", "CH_UP"),
        ("SMARTCAST", "SMARTCAST"),
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_tv_valid(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    command: str,
    expected_key: str,
) -> None:
    """Test send_command resolves valid TV commands."""
    await setup_integration(hass, mock_tv_config_entry)
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
async def test_send_command_tv_invalid(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    command: str,
) -> None:
    """Test send_command raises error for invalid TV commands."""
    await setup_integration(hass, mock_tv_config_entry)
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
        ("MUTE_TOGGLE", "MUTE_TOGGLE"),
        ("pause", "PAUSE"),
        ("VOL_UP", "VOL_UP"),
    ],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_speaker_valid(
    hass: HomeAssistant,
    mock_speaker_config_entry: MockConfigEntry,
    command: str,
    expected_key: str,
) -> None:
    """Test send_command resolves valid speaker commands."""
    await setup_integration(hass, mock_speaker_config_entry)
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


@pytest.mark.parametrize("command", ["MENU", "CH_UP", "INVALID_KEY"])
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_send_command_speaker_invalid(
    hass: HomeAssistant,
    mock_speaker_config_entry: MockConfigEntry,
    command: str,
) -> None:
    """Test speaker remote rejects TV-only and invalid keys."""
    await setup_integration(hass, mock_speaker_config_entry)
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
async def test_send_command_multiple(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test send_command with multiple commands in one call."""
    await setup_integration(hass, mock_tv_config_entry)
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
async def test_send_command_invalid_skips_valid(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test that no commands are sent when one command in the list is invalid."""
    await setup_integration(hass, mock_tv_config_entry)
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
async def test_send_command_delay_between_repeats(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test delay is applied between repeats but not after the last one."""
    await setup_integration(hass, mock_tv_config_entry)
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
