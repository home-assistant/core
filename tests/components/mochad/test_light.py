"""The tests for the mochad light platform."""
import unittest.mock as mock

import pytest

from homeassistant.components import light
from homeassistant.components.mochad import light as mochad
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch("homeassistant.components.mochad.light.device") as device:
        yield device


@pytest.fixture
def light_mock(hass, brightness):
    """Mock light."""
    controller_mock = mock.MagicMock()
    dev_dict = {"address": "a1", "name": "fake_light", "brightness_levels": brightness}
    return mochad.MochadLight(hass, controller_mock, dev_dict)


async def test_setup_adds_proper_devices(hass: HomeAssistant) -> None:
    """Test if setup adds devices."""
    good_config = {
        "mochad": {},
        "light": {
            "platform": "mochad",
            "devices": [{"name": "Light1", "address": "a1"}],
        },
    }
    assert await async_setup_component(hass, light.DOMAIN, good_config)


@pytest.mark.parametrize(
    ("brightness", "expected"), [(32, "on"), (256, "xdim 255"), (64, "xdim 63")]
)
async def test_turn_on_with_no_brightness(light_mock, expected) -> None:
    """Test turn_on."""
    light_mock.turn_on()
    light_mock.light.send_cmd.assert_called_once_with(expected)


@pytest.mark.parametrize(
    ("brightness", "expected"),
    [
        (32, [mock.call("on"), mock.call("dim 25")]),
        (256, [mock.call("xdim 45")]),
        (64, [mock.call("xdim 11")]),
    ],
)
async def test_turn_on_with_brightness(light_mock, expected) -> None:
    """Test turn_on."""
    light_mock.turn_on(brightness=45)
    light_mock.light.send_cmd.assert_has_calls(expected)


@pytest.mark.parametrize("brightness", [32])
async def test_turn_off(light_mock) -> None:
    """Test turn_off."""
    light_mock.turn_off()
    light_mock.light.send_cmd.assert_called_once_with("off")
