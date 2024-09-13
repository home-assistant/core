"""Test the laundrify coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def test_coordinator_update_success(
    hass: HomeAssistant,
    laundrify_config_entry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update is performed successfully."""
    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    assert coordinator.last_update_success


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.UnauthorizedException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    assert not coordinator.last_update_success


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.ApiConnectionException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][laundrify_config_entry.entry_id]["coordinator"]
    assert not coordinator.last_update_success
