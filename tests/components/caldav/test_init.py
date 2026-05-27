"""Unit tests for the CalDav integration."""

from unittest.mock import MagicMock, patch

from caldav.lib.error import AuthorizationError, DAVError
import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def mock_add_to_hass(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture to add the ConfigEntry."""
    config_entry.add_to_hass(hass)


async def test_load_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with patch("homeassistant.components.caldav.config_flow.caldav.DAVClient"):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_session_closes_on_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Underlying HTTP session is torn down when the config entry unloads.

    Regression guard for the lifecycle change that moved socket cleanup from
    per-request ``finally`` blocks to a single ``entry.async_on_unload``
    hook. Multiple in-flight requests share one ``DAVClient.session`` (caldav
    2.1.0+ uses niquests with HTTP/2 multiplexing), so closing the session
    between requests races with concurrent searches; closing it only at
    unload avoids that hazard.
    """
    session = MagicMock()
    with patch(
        "homeassistant.components.caldav.config_flow.caldav.DAVClient"
    ) as mock_client:
        mock_client.return_value.session = session
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED
        session.close.assert_not_called()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    session.close.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_flows"),
    [
        (Exception(), ConfigEntryState.SETUP_ERROR, []),
        (requests.ConnectionError(), ConfigEntryState.SETUP_RETRY, []),
        (requests.Timeout(), ConfigEntryState.SETUP_RETRY, []),
        (DAVError(), ConfigEntryState.SETUP_RETRY, []),
        (
            AuthorizationError(reason="Unauthorized"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
        ),
        (AuthorizationError(reason="Other"), ConfigEntryState.SETUP_ERROR, []),
    ],
)
async def test_client_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_flows: list[str],
) -> None:
    """Test CalDAV client failures in setup."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with patch(
        "homeassistant.components.caldav.config_flow.caldav.DAVClient"
    ) as mock_client:
        mock_client.return_value.principal.side_effect = side_effect
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is expected_state

    flows = hass.config_entries.flow.async_progress()
    assert [flow.get("step_id") for flow in flows] == expected_flows
