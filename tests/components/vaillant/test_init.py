"""Tests for the vaillant HUB."""

import mock
import pytest
from pymultimatic.api import ApiError

from homeassistant.components import vaillant
from homeassistant.components.vaillant import DOMAIN
from tests.components.vaillant import _setup, SystemManagerMock


@pytest.fixture(autouse=True)
def fixture_no_platform(mock_system_manager):
    """Mock vaillant without platform."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = []
    yield
    vaillant.PLATFORMS = orig_platforms


@pytest.fixture(name="mock_init")
def fixture_mock_init():
    """Mock SystemManagerMock constructor."""
    orig_init = SystemManagerMock.__init__
    yield orig_init
    SystemManagerMock.__init__ = orig_init


async def test_invalid_config(hass):
    """Test setup with invalid config."""
    assert not await _setup(hass, {DOMAIN: {'boom': 'boom'}})
    assert not hass.states.async_entity_ids()


async def test_login_failed(hass, mock_init):
    """Test when login fails."""

    def new_init(user: str, password: str, smart_phone_id: str,
                 file_path: str = None):
        mock_init(user, password, smart_phone_id, file_path)
        SystemManagerMock.instance.get_system = \
            mock.MagicMock(side_effect=ApiError('test', None))

    SystemManagerMock.__init__ = new_init
    assert not await _setup(hass)


async def test_hvac_update_fails(hass, mock_init):
    """Test when hvac update request fails."""

    def new_init(user: str, password: str, smart_phone_id: str,
                 file_path: str = None):
        mock_init(user, password, smart_phone_id, file_path)
        SystemManagerMock.instance.request_hvac_update = \
            mock.MagicMock(side_effect=ApiError('test', None))

    SystemManagerMock.__init__ = new_init
    assert await _setup(hass)
