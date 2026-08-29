"""Unit tests for the CalDav integration."""

import logging
from unittest.mock import MagicMock, Mock, patch

from caldav.lib.error import AuthorizationError, DAVError
import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
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


@pytest.fixture(name="calendars")
def mock_unsupported_calendar() -> list[Mock]:
    """Fixture for a calendar that does not report its supported components."""
    calendar = Mock()
    calendar.name = "Example"
    calendar.search = MagicMock(return_value=[])
    calendar.get_supported_components = MagicMock(side_effect=KeyError())
    return [calendar]


@pytest.mark.parametrize("platforms", [[Platform.CALENDAR]])
async def test_supported_components_warning_survives_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the unsupported-components warning is not repeated after a reload.

    The de-duplication cache is per CalDAV server rather than per config entry,
    so reloading the entry must not warn about the same calendar again.
    """
    caplog.set_level(logging.WARNING, logger="homeassistant.components.caldav.api")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert "does not report supported components" in caplog.text

    caplog.clear()
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert "does not report supported components" not in caplog.text
