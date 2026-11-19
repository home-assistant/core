"""Test the Untappd integration setup."""

from unittest.mock import AsyncMock

from aiountappd import UntappdAuthenticationError, UntappdConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.untappd.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


@pytest.mark.usefixtures("mock_untappd_client")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the integration."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (UntappdConnectionError, ConfigEntryState.SETUP_RETRY),
        (UntappdAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_untappd_client: AsyncMock,
    side_effect: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test setup errors."""
    mock_untappd_client.get_user_info.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_untappd_client: AsyncMock,
) -> None:
    """Test an invalid token starts a reauth flow."""
    mock_untappd_client.get_user_info.side_effect = UntappdAuthenticationError
    await setup_integration(hass, mock_config_entry)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_untappd_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when an update fails, and recover."""
    entity_id = "sensor.hopsfan_check_ins"
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(entity_id).state == "1337"

    mock_untappd_client.get_user_checkins.side_effect = UntappdConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_untappd_client.get_user_checkins.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "1337"
