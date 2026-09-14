"""The tests for the mochad switch platform."""

from unittest import mock

from pymochad.exceptions import MochadException
import pytest

from homeassistant.components import switch
from homeassistant.components.mochad import DOMAIN, switch as mochad
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockEntityPlatform


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with (
        mock.patch("homeassistant.components.mochad.switch.device"),
        mock.patch("homeassistant.components.mochad.switch.MochadException"),
    ):
        yield


@pytest.fixture
def switch_mock(hass: HomeAssistant) -> mochad.MochadSwitch:
    """Mock switch."""
    controller_mock = mock.MagicMock()
    dev_dict = {"address": "a1", "name": "fake_switch"}
    entity = mochad.MochadSwitch(hass, controller_mock, dev_dict)
    entity.platform = MockEntityPlatform(hass)
    return entity


async def test_setup_adds_proper_devices(hass: HomeAssistant) -> None:
    """Test if setup adds devices."""
    good_config = {
        "mochad": {},
        "switch": {
            "platform": "mochad",
            "devices": [{"name": "Switch1", "address": "a1"}],
        },
    }
    assert await async_setup_component(hass, switch.DOMAIN, good_config)


async def test_name(switch_mock) -> None:
    """Test the name."""
    assert switch_mock.name == "fake_switch"


async def test_turn_on(switch_mock) -> None:
    """Test turn_on."""
    switch_mock.turn_on()
    switch_mock.switch.send_cmd.assert_called_once_with("on")


async def test_turn_off(switch_mock) -> None:
    """Test turn_off."""
    switch_mock.turn_off()
    switch_mock.switch.send_cmd.assert_called_once_with("off")


@pytest.mark.parametrize(
    ("action", "translation_key"),
    [("turn_on", "turn_on_failed"), ("turn_off", "turn_off_failed")],
)
async def test_action_raises_on_communication_error(
    switch_mock: mochad.MochadSwitch, action: str, translation_key: str
) -> None:
    """Test that a failed action raises instead of being swallowed."""
    with mock.patch(
        "homeassistant.components.mochad.switch.MochadException",
        MochadException,
    ):
        switch_mock.switch.send_cmd.side_effect = MochadException("boom")
        with pytest.raises(HomeAssistantError) as exc_info:
            getattr(switch_mock, action)()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert "error" in exc_info.value.translation_placeholders
