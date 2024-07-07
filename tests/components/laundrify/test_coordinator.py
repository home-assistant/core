"""Test the laundrify coordinator."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant, laundrify_config_entry: MockConfigEntry
) -> None:
    """Test the coordinator update is performed successfully."""
    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant, laundrify_api_mock, laundrify_config_entry: MockConfigEntry
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    laundrify_api_mock.side_effect = exceptions.UnauthorizedException
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant, laundrify_api_mock, laundrify_config_entry: MockConfigEntry
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    laundrify_api_mock.side_effect = exceptions.ApiConnectionException
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
