"""Tests for the WeConnect coordinator."""

from unittest.mock import patch

import pytest
from weconnect.errors import APIError, AuthentificationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_CONFIG_ENTRY
from .conftest import mock_weconnect_login, mock_weconnect_update

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (AuthentificationError, ConfigEntryState.SETUP_ERROR),
        (APIError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_coordinator_login_error(
    hass: HomeAssistant,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Test coordinator with authentication error."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    with patch(
        "weconnect.weconnect.WeConnect.login",
        side_effect=error,
    ) as mock_login:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        assert config_entry.state is state


@patch("weconnect.weconnect.WeConnect.login", mock_weconnect_login)
@patch("weconnect.weconnect.WeConnect.update", mock_weconnect_update)
async def test_coordinator_update_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator with update error."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True

    with patch(
        "weconnect.weconnect.WeConnect.update",
        side_effect=APIError,
    ) as mock_update:
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        mock_update.assert_called_once()
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, UpdateFailed) is True
