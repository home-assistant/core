"""The tests for the Yamaha Media player platform."""

from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.yamaha import media_player as yamaha
from homeassistant.components.yamaha.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component

CONFIG = {"media_player": {"platform": "yamaha", "host": "127.0.0.1"}}


def _create_zone_mock(name, url):
    zone = MagicMock()
    zone.ctrl_url = url
    zone.surround_programs = []
    zone.zone = name
    return zone


class FakeYamahaDevice:
    """A fake Yamaha device."""

    def __init__(self, ctrl_url, name, zones=None):
        """Initialize the fake Yamaha device."""
        self.ctrl_url = ctrl_url
        self.name = name
        self._zones = zones or []

    def zone_controllers(self):
        """Return controllers for all available zones."""
        return self._zones


@pytest.fixture(name="main_zone")
def main_zone_fixture():
    """Mock the main zone."""
    return _create_zone_mock("Main zone", "http://main")


@pytest.fixture(name="device")
def device_fixture(main_zone):
    """Mock the yamaha device."""
    device = FakeYamahaDevice("http://receiver", "Receiver", zones=[main_zone])
    with patch("rxv.RXV", return_value=device):
        yield device


async def test_setup_host(hass: HomeAssistant, device, main_zone) -> None:
    """Test set up integration with host."""
    assert await async_setup_component(hass, MP_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_no_host(hass: HomeAssistant, device, main_zone) -> None:
    """Test set up integration without host."""
    with patch("rxv.find", return_value=[device]):
        assert await async_setup_component(
            hass, MP_DOMAIN, {"media_player": {"platform": "yamaha"}}
        )
        await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_discovery(hass: HomeAssistant, device, main_zone) -> None:
    """Test set up integration via discovery."""
    discovery_info = {
        "name": "Yamaha Receiver",
        "model_name": "Yamaha",
        "control_url": "http://receiver",
        "description_url": "http://receiver/description",
    }
    await async_load_platform(
        hass, MP_DOMAIN, "yamaha", discovery_info, {MP_DOMAIN: {}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_zone_ignore(hass: HomeAssistant, device, main_zone) -> None:
    """Test set up integration without host."""
    assert await async_setup_component(
        hass,
        MP_DOMAIN,
        {
            "media_player": {
                "platform": "yamaha",
                "host": "127.0.0.1",
                "zone_ignore": "Main zone",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is None


async def test_enable_output(hass: HomeAssistant, device, main_zone) -> None:
    """Test enable output service."""
    assert await async_setup_component(hass, MP_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    port = "hdmi1"
    enabled = True
    data = {
        "entity_id": "media_player.yamaha_receiver_main_zone",
        "port": port,
        "enabled": enabled,
    }

    await hass.services.async_call(DOMAIN, yamaha.SERVICE_ENABLE_OUTPUT, data, True)

    assert main_zone.enable_output.call_count == 1
    assert main_zone.enable_output.call_args == call(port, enabled)


@pytest.mark.parametrize(
    ("cursor", "method"),
    [
        (yamaha.CURSOR_TYPE_DOWN, "menu_down"),
        (yamaha.CURSOR_TYPE_LEFT, "menu_left"),
        (yamaha.CURSOR_TYPE_RETURN, "menu_return"),
        (yamaha.CURSOR_TYPE_RIGHT, "menu_right"),
        (yamaha.CURSOR_TYPE_SELECT, "menu_sel"),
        (yamaha.CURSOR_TYPE_UP, "menu_up"),
    ],
)
@pytest.mark.usefixtures("device")
async def test_menu_cursor(hass: HomeAssistant, main_zone, cursor, method) -> None:
    """Verify that the correct menu method is called for the menu_cursor service."""
    assert await async_setup_component(hass, MP_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    data = {
        "entity_id": "media_player.yamaha_receiver_main_zone",
        "cursor": cursor,
    }
    await hass.services.async_call(DOMAIN, yamaha.SERVICE_MENU_CURSOR, data, True)

    getattr(main_zone, method).assert_called_once_with()


async def test_select_scene(
    hass: HomeAssistant, device, main_zone, caplog: pytest.LogCaptureFixture
) -> None:
    """Test select scene service."""
    scene_prop = PropertyMock(return_value=None)
    type(main_zone).scene = scene_prop

    assert await async_setup_component(hass, MP_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    scene = "TV Viewing"
    data = {
        "entity_id": "media_player.yamaha_receiver_main_zone",
        "scene": scene,
    }

    await hass.services.async_call(DOMAIN, yamaha.SERVICE_SELECT_SCENE, data, True)

    assert scene_prop.call_count == 1
    assert scene_prop.call_args == call(scene)

    scene = "BD/DVD Movie Viewing"
    data["scene"] = scene

    await hass.services.async_call(DOMAIN, yamaha.SERVICE_SELECT_SCENE, data, True)

    assert scene_prop.call_count == 2
    assert scene_prop.call_args == call(scene)

    scene_prop.side_effect = AssertionError()

    missing_scene = "Missing scene"
    data["scene"] = missing_scene

    await hass.services.async_call(DOMAIN, yamaha.SERVICE_SELECT_SCENE, data, True)

    assert f"Scene '{missing_scene}' does not exist!" in caplog.text
