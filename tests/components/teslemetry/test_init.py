"""Test the Tessie init."""

from tesla_fleet_api.exceptions import InvalidToken, PaymentRequired, TeslaFleetError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_platform


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(hass: HomeAssistant, mock_teslemetry) -> None:
    """Test init with an authentication error."""

    mock_teslemetry.return_value.products.side_effect = InvalidToken
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_subscription_failure(hass: HomeAssistant, mock_teslemetry) -> None:
    """Test init with an client response error."""

    mock_teslemetry.return_value.products.side_effect = PaymentRequired
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_other_failure(hass: HomeAssistant, mock_teslemetry) -> None:
    """Test init with an client response error."""

    mock_teslemetry.return_value.products.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
