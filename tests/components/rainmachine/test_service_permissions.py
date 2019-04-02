"""Define tests for permissions on RainMachine service calls."""
import asynctest
import pytest

from homeassistant.components.rainmachine.const import DOMAIN
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.setup import async_setup_component

from tests.common import mock_coro


async def setup_platform(hass, config_entry):
    """Set up the media player platform for testing."""
    with asynctest.mock.patch('regenmaschine.login') as mock_login:
        mock_client = mock_login.return_value
        mock_client.restrictions.current.return_value = mock_coro()
        mock_client.restrictions.universal.return_value = mock_coro()
        config_entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN)
        await hass.async_block_till_done()


async def test_services_authorization(
        hass, config_entry, hass_read_only_user):
    """Test that a RainMachine service is halted on incorrect permissions."""
    await setup_platform(hass, config_entry)

    with pytest.raises(UnknownUser):
        await hass.services.async_call(
            'rainmachine',
            'unpause_watering', {},
            blocking=True,
            context=Context(user_id='fake_user_id'))

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            'rainmachine',
            'unpause_watering', {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id))
