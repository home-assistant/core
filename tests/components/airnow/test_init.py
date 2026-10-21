"""Test the AirNow integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyairnow.errors import InvalidKeyError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=InvalidKeyError)])
@pytest.mark.usefixtures("setup_airnow")
async def test_setup_auth_failed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test an invalid API key during setup starts a reauth flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


async def test_update_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_get: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an invalid API key during a scheduled refresh starts a reauth flow."""
    # Sensor platform is needed so the coordinator has listeners and polls
    with patch("pyairnow.WebServiceAPI._get", mock_api_get):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        mock_api_get.side_effect = InvalidKeyError
        freezer.tick(timedelta(minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id
