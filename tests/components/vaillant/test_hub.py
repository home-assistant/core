"""Tests for the hub."""
from asynctest import CoroutineMock
from pymultimatic.api import ApiError
import pytest

import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import ApiHub

from tests.components.vaillant import SystemManagerMock
from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture(autouse=True)
def fixture_nothing(mock_system_manager):
    """Mock System Manager."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = []
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_authenticate_error(hass):
    """Test authentication gives error."""
    response = AiohttpClientMockResponse("GET", "http://test.com", json={})
    SystemManagerMock.login = CoroutineMock(side_effect=ApiError("test", response, {}))
    hub = ApiHub(hass, "user", "pwd", None)
    hub._manager = SystemManagerMock

    assert not await hub.authenticate()


async def test_authenticate_ok(hass):
    """Test correct credentials."""
    SystemManagerMock.login = CoroutineMock(return_value=True)
    hub = ApiHub(hass, "user", "pwd", None)

    assert await hub.authenticate()


async def test_request_hvac_ok(hass):
    """Test hvac request went well."""
    SystemManagerMock.request_hvac_update = CoroutineMock(return_value=True)
    hub = ApiHub(hass, "user", "pwd", None)
    hub._manager = SystemManagerMock

    await hub.request_hvac_update()
    SystemManagerMock.request_hvac_update.assert_awaited()


async def test_request_hvac_error(hass):
    """Test hvac request gives error and new authentication occurred."""
    response = AiohttpClientMockResponse("GET", "http://test.com", json={}, status=401)
    SystemManagerMock.request_hvac_update = CoroutineMock(
        side_effect=ApiError("test", response, {})
    )
    hub = ApiHub(hass, "user", "pwd", None)
    hub.authenticate = CoroutineMock()
    hub._manager = SystemManagerMock

    await hub.request_hvac_update()
    hub.authenticate.assert_awaited()


async def test_request_hvac_error_409(hass):
    """Test hvac request gives HTTP 409 and authentication didn't occur."""
    response = AiohttpClientMockResponse("GET", "http://test.com", json={}, status=409)
    SystemManagerMock.request_hvac_update = CoroutineMock(
        side_effect=ApiError("test", response, {})
    )
    hub = ApiHub(hass, "user", "pwd", None)
    hub.authenticate = CoroutineMock()
    hub._manager = SystemManagerMock

    await hub.request_hvac_update()
    hub.authenticate.assert_not_awaited()


async def test_update_system_ok(hass):
    """Test update system is ok."""
    hub = ApiHub(hass, "user", "pwd", None)
    hub.authenticate = CoroutineMock()

    SystemManagerMock.get_system = CoroutineMock()
    hub._manager = SystemManagerMock

    await hub._update_system()
    hub.authenticate.assert_not_awaited()


async def test_update_system_error(hass):
    """Test system update gives error and triggers authentication."""
    hub = ApiHub(hass, "user", "pwd", None)
    hub.authenticate = CoroutineMock()

    response = AiohttpClientMockResponse("GET", "http://test.com", json={}, status=401)
    SystemManagerMock.get_system = CoroutineMock(
        side_effect=ApiError("test", response, {})
    )
    hub._manager = SystemManagerMock

    await hub._update_system()
    hub.authenticate.assert_awaited()
