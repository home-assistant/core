"""Tests for common vera code."""
from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.vera import SubscriptionRegistry
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_subscription_registry(hass: HomeAssistant) -> None:
    """Test subscription registry polling."""
    subscription_registry = SubscriptionRegistry(hass)
    subscription_registry.poll_server_once = poll_server_once_mock = MagicMock()

    poll_server_once_mock.return_value = True
    await hass.async_add_executor_job(subscription_registry.start)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    poll_server_once_mock.assert_called_once()

    # Last poll was successful and already scheduled the next poll for 1s in the future.
    # This will ensure that future poll will fail.
    poll_server_once_mock.return_value = False

    # Asserting future poll runs.
    poll_server_once_mock.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    poll_server_once_mock.assert_called_once()

    # Asserting a future poll is delayed due to the failure set above.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=2))
    poll_server_once_mock.reset_mock()
    poll_server_once_mock.assert_not_called()

    poll_server_once_mock.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    poll_server_once_mock.assert_called_once()

    poll_server_once_mock.reset_mock()
    await hass.async_add_executor_job(subscription_registry.stop)

    # Assert no further polling is performed.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=65))
    await hass.async_block_till_done()
    poll_server_once_mock.assert_not_called()
