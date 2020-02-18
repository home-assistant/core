"""Test Dynalite light."""
from unittest.mock import Mock

from asynctest import CoroutineMock, patch
import pytest

from homeassistant.components import dynalite
from homeassistant.components.light import SUPPORT_BRIGHTNESS
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_device():
    """Mock a Dynalite device."""
    device = Mock()
    device.category = "light"
    device.unique_id = "UNIQUE"
    device.name = "NAME"
    device.device_info = {
        "identifiers": {(dynalite.DOMAIN, device.unique_id)},
        "name": device.name,
        "manufacturer": "Dynalite",
    }
    return device


async def create_light_from_device(hass, device):
    """Set up the component and platform and create a light based on the device provided."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {dynalite.DOMAIN: {dynalite.CONF_BRIDGES: [{dynalite.CONF_HOST: host}]}},
        )
    await hass.async_block_till_done()
    # Find the bridge
    bridge = None
    assert len(hass.data[dynalite.DOMAIN]) == 1
    key = next(iter(hass.data[dynalite.DOMAIN]))
    bridge = hass.data[dynalite.DOMAIN][key]
    bridge.dynalite_devices.newDeviceFunc([device])
    await hass.async_block_till_done()


async def test_light_setup(hass, mock_device):
    """Test a successful setup."""
    await create_light_from_device(hass, mock_device)
    entity_state = hass.states.get("light.name")
    assert entity_state.attributes["brightness"] == mock_device.brightness
    assert entity_state.attributes["supported_features"] == SUPPORT_BRIGHTNESS


async def test_turn_on(hass, mock_device):
    """Test turning a light on."""
    mock_device.async_turn_on = CoroutineMock(return_value=True)
    await create_light_from_device(hass, mock_device)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.name"}, blocking=True
    )
    await hass.async_block_till_done()
    mock_device.async_turn_on.assert_awaited_once()


async def test_turn_off(hass, mock_device):
    """Test turning a light off."""
    mock_device.async_turn_off = CoroutineMock(return_value=True)
    await create_light_from_device(hass, mock_device)
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.name"}, blocking=True
    )
    await hass.async_block_till_done()
    mock_device.async_turn_off.assert_awaited_once()
