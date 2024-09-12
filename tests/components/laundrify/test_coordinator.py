"""Test the laundrify coordinator."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL
from homeassistant.components.laundrify.coordinator import LaundrifyUpdateCoordinator
from homeassistant.core import HomeAssistant


async def test_coordinator_update_success(
    hass: HomeAssistant, laundrify_api_mock
) -> None:
    """Test the coordinator update is performed successfully."""
    coordinator = LaundrifyUpdateCoordinator(
        hass, laundrify_api_mock, DEFAULT_POLL_INTERVAL
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant, laundrify_api_mock
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    coordinator = LaundrifyUpdateCoordinator(
        hass, laundrify_api_mock, DEFAULT_POLL_INTERVAL
    )
    laundrify_api_mock.get_machines.side_effect = exceptions.UnauthorizedException

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant, laundrify_api_mock
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    coordinator = LaundrifyUpdateCoordinator(
        hass, laundrify_api_mock, DEFAULT_POLL_INTERVAL
    )
    laundrify_api_mock.get_machines.side_effect = exceptions.ApiConnectionException

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
