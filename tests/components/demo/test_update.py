"""The tests for the demo update platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_demo_update(hass: HomeAssistant) -> None:
    """Initialize setup demo update entity."""
    assert await async_setup_component(hass, DOMAIN, {"update": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get("update.demo_update_no_install")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_TITLE] == "Awesomesoft Inc."
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY] == "Awesome update, fixing everything!"
    )
    assert state.attributes[ATTR_RELEASE_URL] == "https://www.example.com/release/1.0.1"
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/demo/icon.png"
    )

    state = hass.states.get("update.demo_no_update")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_TITLE] == "AdGuard Home"
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/demo/icon.png"
    )

    state = hass.states.get("update.demo_add_on")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_TITLE] == "AdGuard Home"
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY] == "Awesome update, fixing everything!"
    )
    assert state.attributes[ATTR_RELEASE_URL] == "https://www.example.com/release/1.0.1"
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/demo/icon.png"
    )

    state = hass.states.get("update.demo_living_room_bulb_update")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_TITLE] == "Philips Lamps Firmware"
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.93.3"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.94.2"
    assert state.attributes[ATTR_RELEASE_SUMMARY] == "Added support for effects"
    assert (
        state.attributes[ATTR_RELEASE_URL] == "https://www.example.com/release/1.93.3"
    )
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/demo/icon.png"
    )

    state = hass.states.get("update.demo_update_with_progress")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_TITLE] == "Philips Lamps Firmware"
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.93.3"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.94.2"
    assert state.attributes[ATTR_RELEASE_SUMMARY] == "Added support for effects"
    assert (
        state.attributes[ATTR_RELEASE_URL] == "https://www.example.com/release/1.93.3"
    )
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/demo/icon.png"
    )


async def test_update_with_progress(hass: HomeAssistant) -> None:
    """Test update with progress."""
    state = hass.states.get("update.demo_update_with_progress")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False

    events = []
    async_track_state_change_event(
        hass,
        "update.demo_update_with_progress",
        callback(lambda event: events.append(event)),
    )

    with patch("homeassistant.components.demo.update.FAKE_INSTALL_SLEEP_TIME", new=0):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.demo_update_with_progress"},
            blocking=True,
        )

    assert len(events) == 10
    assert events[0].data["new_state"].state == STATE_ON
    assert events[0].data["new_state"].attributes[ATTR_IN_PROGRESS] == 10
    assert events[1].data["new_state"].attributes[ATTR_IN_PROGRESS] == 20
    assert events[2].data["new_state"].attributes[ATTR_IN_PROGRESS] == 30
    assert events[3].data["new_state"].attributes[ATTR_IN_PROGRESS] == 40
    assert events[4].data["new_state"].attributes[ATTR_IN_PROGRESS] == 50
    assert events[5].data["new_state"].attributes[ATTR_IN_PROGRESS] == 60
    assert events[6].data["new_state"].attributes[ATTR_IN_PROGRESS] == 70
    assert events[7].data["new_state"].attributes[ATTR_IN_PROGRESS] == 80
    assert events[8].data["new_state"].attributes[ATTR_IN_PROGRESS] == 90
    assert events[9].data["new_state"].attributes[ATTR_IN_PROGRESS] is False
    assert events[9].data["new_state"].state == STATE_OFF


async def test_update_with_progress_raising(hass: HomeAssistant) -> None:
    """Test update with progress failing to install."""
    state = hass.states.get("update.demo_update_with_progress")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False

    events = []
    async_track_state_change_event(
        hass,
        "update.demo_update_with_progress",
        callback(lambda event: events.append(event)),
    )

    with patch(
        "homeassistant.components.demo.update._fake_install",
        side_effect=[None, None, None, None, RuntimeError],
    ) as fake_sleep, pytest.raises(RuntimeError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.demo_update_with_progress"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert fake_sleep.call_count == 5
    assert len(events) == 5
    assert events[0].data["new_state"].state == STATE_ON
    assert events[0].data["new_state"].attributes[ATTR_IN_PROGRESS] == 10
    assert events[1].data["new_state"].attributes[ATTR_IN_PROGRESS] == 20
    assert events[2].data["new_state"].attributes[ATTR_IN_PROGRESS] == 30
    assert events[3].data["new_state"].attributes[ATTR_IN_PROGRESS] == 40
    assert events[4].data["new_state"].attributes[ATTR_IN_PROGRESS] is False
    assert events[4].data["new_state"].state == STATE_ON
