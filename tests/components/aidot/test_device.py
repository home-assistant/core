"""Test the aidot device."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.aidot.light import AidotLight
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def mock_hass():
    """Fixture for HomeAssistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.loop = asyncio.get_event_loop()
    hass.bus = Mock()
    hass.bus.async_listen = AsyncMock()
    hass.bus.async_listen_once = AsyncMock()
    return hass


@pytest.fixture
def mock_device():
    """Fixture for a mock device."""
    return {
        "id": "device_id",
        "name": "Test Light",
        "modelId": "aidot.light.rgbw",
        "mac": "AA:BB:CC:DD:EE:FF",
        "hardwareVersion": "1.0",
        "type": "light",
        "aesKey": ["mock_aes_key"],
    }


@pytest.fixture
def mock_user_info():
    """Fixture for mock user information."""
    return {"user_id": "user_id", "access_token": "mock_access_token"}


@pytest.fixture
def mock_lan_ctrl():
    """Fixture for a mock Lan controller."""
    mock_lan_ctrl = Mock()
    mock_lan_ctrl.connectAndLogin = True
    mock_lan_ctrl.available = True
    mock_lan_ctrl.is_on = True
    mock_lan_ctrl.brightness = 255
    mock_lan_ctrl.cct = 3000
    mock_lan_ctrl.rgdb = 0xFFFFFFFF
    mock_lan_ctrl.colorMode = "rgbw"
    mock_lan_ctrl.sendDevAttr = AsyncMock()
    mock_lan_ctrl.getDimingAction = Mock(return_value={"dim": 100})
    mock_lan_ctrl.getCCTAction = Mock(return_value={"cct": 3000})
    mock_lan_ctrl.getRGBWAction = Mock(return_value={"rgbw": 0xFFFFFFFF})
    mock_lan_ctrl.getOnOffAction = Mock(return_value={"OnOff": 1})
    return mock_lan_ctrl


@pytest.fixture
def aidot_light(mock_hass, mock_device, mock_user_info, mock_lan_ctrl, monkeypatch):
    """Fixture for AidotLight instance."""
    monkeypatch.setattr(
        "homeassistant.components.aidot.light.Lan",
        lambda *args, **kwargs: mock_lan_ctrl,
    )
    return AidotLight(mock_hass, mock_device, mock_user_info)


@pytest.mark.asyncio
async def test_turn_on_with_brightness(aidot_light) -> None:
    """Test turning on the light with brightness."""
    await aidot_light.async_turn_on(brightness=128)
    aidot_light.lanCtrl.sendDevAttr.assert_called_once_with({"dim": 100})


@pytest.mark.asyncio
async def test_turn_on_with_color_temp(aidot_light) -> None:
    """Test turning on the light with color temperature."""
    await aidot_light.async_turn_on(color_temp_kelvin=3000)
    aidot_light.lanCtrl.sendDevAttr.assert_called_once_with({"cct": 3000})


@pytest.mark.asyncio
async def test_turn_on_with_rgbw(aidot_light) -> None:
    """Test turning on the light with RGBW color."""
    await aidot_light.async_turn_on(rgbw_color=(255, 255, 255, 255))
    aidot_light.lanCtrl.sendDevAttr.assert_called_once_with({"rgbw": 0xFFFFFFFF})


@pytest.mark.asyncio
async def test_turn_on(aidot_light) -> None:
    """Test turning on the light."""
    await aidot_light.async_turn_on()
    aidot_light.lanCtrl.sendDevAttr.assert_called_once_with({"OnOff": 1})


@pytest.mark.asyncio
async def test_turn_off(aidot_light) -> None:
    """Test turning off the light."""
    await aidot_light.async_turn_off()
    aidot_light.lanCtrl.sendDevAttr.assert_called_once_with({"OnOff": 1})


@pytest.mark.asyncio
async def test_turn_on_not_logged_in(aidot_light, mock_lan_ctrl) -> None:
    """Test turning on the light when not logged in."""
    mock_lan_ctrl.connectAndLogin = False
    with pytest.raises(HomeAssistantError):
        await aidot_light.async_turn_on()
