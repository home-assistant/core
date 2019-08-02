import mock
from vr900connector.api import ApiError

from homeassistant.components.vaillant import DOMAIN
from tests.components.vaillant import _setup, SystemManagerMock


async def test_invalid_config(hass):
    """Test setup with invalid config."""
    assert not await _setup(hass, {DOMAIN: {'boom': 'boom'}})
    assert not hass.states.async_entity_ids()


# async def test_login_failed(hass):
#     """Test when login fails"""
#     SystemManagerMock.get_system = mock.MagicMock(side_effect=
#                                                   ApiError('test', None))
#     assert not await _setup(hass)


# async def test_hvac_update_fails(hass):
#     """Test when hvac update request fails"""
#     SystemManagerMock.request_hvac_update = \
#         mock.MagicMock(side_effect=ApiError('test', None))
#     assert await _setup(hass)
#     assert False
