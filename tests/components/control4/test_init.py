"""Test the Control4 integration setup."""

from json import JSONDecodeError
from unittest.mock import MagicMock

from pyControl4.error_handling import BadCredentials, C4Exception
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.CLIMATE, Platform.COVER, Platform.LIGHT, Platform.MEDIA_PLAYER]


async def test_setup_bad_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_account: MagicMock,
) -> None:
    """Test setup fails with invalid credentials."""
    mock_c4_account.get_account_bearer_token.side_effect = BadCredentials(
        "Invalid credentials"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        "Error authenticating with the Control4 account API, incorrect username or"
        " password"
    )


@pytest.mark.usefixtures("mock_c4_account")
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(C4Exception("director unavailable"), id="api_error"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(JSONDecodeError("Expecting value", "", 0), id="invalid_json"),
    ],
)
async def test_setup_retries_when_first_poll_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_director: MagicMock,
    exception: Exception,
) -> None:
    """Test setup is retried when the director does not answer the first poll."""
    mock_c4_director.get_all_item_variable_value.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_all() == []


@pytest.mark.usefixtures("mock_c4_account", "mock_room_variables")
async def test_setup_when_only_rooms_have_variables(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds when no item has the climate, cover or light variables."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids() == ["media_player.living_room"]
