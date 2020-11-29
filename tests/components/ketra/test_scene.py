"""Tests for the Ketra Scene platform."""

import logging

from aioketraapi.models import ButtonChange, ButtonChangeNotification, HubReady
import pytest

from homeassistant.components.ketra import DOMAIN as KETRA_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, SERVICE_TURN_ON
from homeassistant.helpers.entity_platform import async_get_platforms

from .common import SCENE_ENTITY_ID, MockHub, setup_platform

from tests.async_mock import patch

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(name="config_entry")
async def setup_config_entry(hass):
    """Set up config entry."""
    hub = MockHub()

    async def patched_get_hub(*args, **kwargs):
        return hub

    with patch("aioketraapi.n4_hub.N4Hub.get_hub", new=patched_get_hub), patch(
        "homeassistant.components.ketra.KETRA_PLATFORMS", ["scene"]
    ), patch("homeassistant.components.ketra.WEBSOCKET_RECONNECT_DELAY", 0.1):
        entry = await setup_platform(hass)
        yield entry


@pytest.fixture(name="platform_common")
async def setup_scene_platform(hass, config_entry):
    """Set up platform."""
    cmn_plat = hass.data[KETRA_DOMAIN][config_entry.unique_id]["common_platform"]
    yield cmn_plat
    await cmn_plat.shutdown()


async def test_scene_platform_creation(hass, config_entry, platform_common):
    """Test platform creation."""
    assert len(platform_common.platforms) == 1
    entries = hass.config_entries.async_entries(KETRA_DOMAIN)
    assert len(entries) == 1
    state = hass.states.get(f"{SCENE_DOMAIN}.{SCENE_ENTITY_ID}")
    assert state is not None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == SCENE_ENTITY_ID
    scene_platform = async_get_platforms(hass, KETRA_DOMAIN)[0]
    assert len(scene_platform.entities) == 1


async def test_scene_entity_refresh(hass, platform_common):
    """Test platform refresh."""
    await platform_common.platforms[0].refresh_entity_state()
    assert len(platform_common.platforms[0].button_map) == 1
    entries = hass.config_entries.async_entries(KETRA_DOMAIN)
    assert len(entries) == 1
    # verify that we have 1 entity
    scene_platform = async_get_platforms(hass, KETRA_DOMAIN)[0]
    assert len(scene_platform.entities) == 1


async def test_scene_reload_platform(hass, platform_common):
    """Test platform reload."""
    platform_common.hub.add_keypad_button()
    await platform_common.platforms[0].reload_platform()
    assert len(platform_common.platforms[0].button_map) == 2
    await hass.async_block_till_done()
    # verify that we have 2 entities
    scene_platform = async_get_platforms(hass, KETRA_DOMAIN)[0]
    assert len(scene_platform.entities) == 2


async def test_scene_reload_platform_via_hubready(hass, platform_common):
    """Test platform reload."""
    platform_common.hub.add_keypad_button()
    await platform_common.platforms[0].websocket_notification(
        HubReady(notification_type="HubReady", time_utc="now")
    )
    assert len(platform_common.platforms[0].button_map) == 2
    await hass.async_block_till_done()
    scene_platform = async_get_platforms(hass, KETRA_DOMAIN)[0]
    assert len(scene_platform.entities) == 2


async def test_scene_removed(hass, platform_common):
    """Test platform reload."""
    platform_common.hub.remove_keypad_buttons()
    await platform_common.platforms[0].reload_platform()
    assert len(platform_common.platforms[0].button_map) == 0
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(KETRA_DOMAIN)
    assert len(entries) == 1
    scene_platform = async_get_platforms(hass, KETRA_DOMAIN)[0]
    assert len(scene_platform.entities) == 0


async def test_scene_activation(hass, platform_common):
    """Test scene activation."""
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"{SCENE_DOMAIN}.{SCENE_ENTITY_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()
    platform_common.hub.button.activate.assert_called_once()


async def test_scene_websocket_button_change_notification(hass, platform_common):
    """Test scene notification."""
    notifications = []

    def listener(event):
        notifications.append(event)

    # listen for ketra_button_press
    hass.bus.async_listen("ketra_button_press", listener)

    btn_change = ButtonChange(
        notification_type="ButtonChange",
        time_utc="now",
        contents=ButtonChangeNotification(button_id="12345", activated=True),
    )
    await platform_common.platforms[0].websocket_notification(btn_change)
    await hass.async_block_till_done()
    assert len(notifications) == 1
    assert notifications[0].event_type == "ketra_button_press"
    assert notifications[0].data["button_id"] == "12345"
    assert notifications[0].data["name"] == "ketra_scene_name"
    assert notifications[0].data["keypad_name"] == "keypad name"
    assert notifications[0].data["activated"]


async def test_scene_websocket_button_change_invalid_notification(
    hass, platform_common
):
    """Test invalid scene notification."""
    notifications = []

    def listener(event):
        notifications.append(event)

    # listen for ketra_button_press
    hass.bus.async_listen("ketra_button_press", listener)
    btn_change = ButtonChange(
        notification_type="ButtonChange",
        time_utc="now",
        contents=ButtonChangeNotification(button_id="123456", activated=True),
    )
    await platform_common.platforms[0].websocket_notification(btn_change)
    await hass.async_block_till_done()
    assert len(notifications) == 0
