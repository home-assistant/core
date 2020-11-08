"""The tests for the Yamaha Media player platform."""
import pytest

import rxv

import homeassistant.components.media_player as mp
from homeassistant.components.yamaha import media_player as yamaha
from homeassistant.components.yamaha.const import DOMAIN
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, PropertyMock, call, patch

CONFIG = {"media_player": {"platform": "yamaha", "host": "127.0.0.1"}}
CONFIG_WITH_IGNORED_SOURCES = {
    "media_player": {
        "platform": "yamaha",
        "host": "127.0.0.1",
        "source_ignore": ["NET RADIO"],
    }
}
CONFIG_WITH_RENAMED_SOURCES = {
    "media_player": {
        "platform": "yamaha",
        "host": "127.0.0.1",
        "source_names": {"AV1": "Karaoke"},
    }
}


def _create_zone_mock(name, url):
    zone = MagicMock(spec=rxv.RXV)
    zone.ctrl_url = url
    zone.zone = name

    zone.inputs.return_value = {
        "AV1": None,
        "AV2": None,
        "NET RADIO": "NET_RADIO",
        "HDMI1": "Osdname:Test Device",
    }

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


async def test_setup_host(hass, device, main_zone):
    """Test set up integration with host."""
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_no_host(hass, device, main_zone):
    """Test set up integration without host."""
    with patch("rxv.find", return_value=[device]):
        assert await async_setup_component(
            hass, mp.DOMAIN, {"media_player": {"platform": "yamaha"}}
        )
        await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_discovery(hass, device, main_zone):
    """Test set up integration via discovery."""
    discovery_info = {
        "name": "Yamaha Receiver",
        "model_name": "Yamaha",
        "control_url": "http://receiver",
        "description_url": "http://receiver/description",
    }
    await async_load_platform(
        hass, mp.DOMAIN, "yamaha", discovery_info, {mp.DOMAIN: {}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")

    assert state is not None
    assert state.state == "off"


async def test_setup_zone_ignore(hass, device, main_zone):
    """Test set up integration without host."""
    assert await async_setup_component(
        hass,
        mp.DOMAIN,
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


async def test_enable_output(hass, device, main_zone):
    """Test enable output service."""
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
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


async def test_select_scene(hass, device, main_zone, caplog):
    """Test select scene service."""
    scene_prop = PropertyMock(return_value=None)
    type(main_zone).scene = scene_prop

    assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
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


async def test_sources(hass, device):
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")
    assert state is not None

    main_zone = hass.data[mp.DOMAIN].get_entity(
        "media_player.yamaha_receiver_main_zone"
    )
    assert main_zone

    main_zone.update()
    assert len(main_zone.source_list) == 4
    assert main_zone.source_list == ["AV1", "AV2", "NET RADIO", "Test Device"]


async def test_sources_ignored(hass, device):
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG_WITH_IGNORED_SOURCES)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")
    assert state is not None

    main_zone = hass.data[mp.DOMAIN].get_entity(
        "media_player.yamaha_receiver_main_zone"
    )
    assert main_zone

    main_zone.update()
    assert len(main_zone.source_list) == 3
    assert main_zone.source_list == ["AV1", "AV2", "Test Device"]


async def test_sources_renamed(hass, device):
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG_WITH_RENAMED_SOURCES)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.yamaha_receiver_main_zone")
    assert state is not None

    main_zone = hass.data[mp.DOMAIN].get_entity(
        "media_player.yamaha_receiver_main_zone"
    )
    assert main_zone

    main_zone.update()
    assert len(main_zone.source_list) == 4
    assert main_zone.source_list == ["AV2", "Karaoke", "NET RADIO", "Test Device"]
