"""Test the laundrify coordinator."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import create_entry


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Test the coordinator update is performed successfully."""
    config_entry = create_entry(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant, laundrify_api_mock
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    config_entry = create_entry(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    laundrify_api_mock.side_effect = exceptions.UnauthorizedException
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant, laundrify_api_mock
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    config_entry = create_entry(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    laundrify_api_mock.side_effect = exceptions.ApiConnectionException
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
