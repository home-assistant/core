"""Test the laundrify coordinator."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    _patch_laundrify_get_machines,
    _patch_laundrify_validate_token,
    create_entry,
)


async def test_coordinator_update_success(hass: HomeAssistant):
    """Test the coordinator update is performed successfully."""
    with _patch_laundrify_validate_token(), _patch_laundrify_get_machines():
        config_entry = create_entry(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_unauthorized(hass: HomeAssistant):
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    with _patch_laundrify_validate_token(), _patch_laundrify_get_machines() as coordinator_mock:
        config_entry = create_entry(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        coordinator_mock.side_effect = exceptions.UnauthorizedException
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not coordinator.last_update_success


async def test_coordinator_update_connection_failed(hass: HomeAssistant):
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    with _patch_laundrify_validate_token(), _patch_laundrify_get_machines() as coordinator_mock:
        config_entry = create_entry(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        coordinator_mock.side_effect = exceptions.ApiConnectionException
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
