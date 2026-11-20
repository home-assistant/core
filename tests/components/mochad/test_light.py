"""The tests for the mochad light platform."""

from unittest import mock

from pymochad.exceptions import MochadException
import pytest

from homeassistant.components import light
from homeassistant.components.mochad import DOMAIN, light as mochad
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch("homeassistant.components.mochad.light.device") as device:
        yield device


@pytest.fixture
def light_mock(hass: HomeAssistant, brightness: int) -> mochad.MochadLight:
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


@pytest.mark.parametrize(
    ("brightness", "action", "translation_key"),
    [(32, "turn_on", "turn_on_failed"), (32, "turn_off", "turn_off_failed")],
)
async def test_action_raises_on_communication_error(
    light_mock: mochad.MochadLight, action: str, translation_key: str
) -> None:
    """Test that a failed action raises instead of being swallowed."""
    light_mock.light.send_cmd.side_effect = MochadException("boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        getattr(light_mock, action)()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert "error" in exc_info.value.translation_placeholders
