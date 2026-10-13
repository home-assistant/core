"""Test the Powerfox data update coordinators."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from powerfox import PowerfoxAuthenticationError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("method", ["device", "report"])
async def test_transient_authentication_error(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test transient authentication errors do not trigger reauthentication."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("method", ["device", "report"])
async def test_persistent_authentication_error(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test persistent authentication errors trigger reauthentication."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=70))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_recheck_succeeds(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test successful credential recheck prevents reauthentication."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=70))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count >= 2
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_failure_timer_resets(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test successful updates reset the authentication failure timer."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)

    # First authentication failure.
    api_method.side_effect = PowerfoxAuthenticationError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Successful update resets the timer.
    api_method.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A new authentication failure starts a fresh timer.
    api_method.side_effect = PowerfoxAuthenticationError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Only 50 seconds have passed since the new failure.
    freezer.tick(timedelta(seconds=50))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count == 1
    assert not hass.config_entries.flow.async_progress()
