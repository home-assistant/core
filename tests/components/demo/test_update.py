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
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component


@pytest.fixture
async def update_only() -> None:
    """Enable only the update platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.UPDATE],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_update(hass: HomeAssistant, update_only) -> None:
    """Initialize setup demo update entity."""
    assert await async_setup_component(
        hass, UPDATE_DOMAIN, {"update": {"platform": "demo"}}
    )
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


@pytest.mark.parametrize(
    ("entity_id", "steps"),
    [
        ("update.demo_update_with_progress", 10),
        ("update.demo_update_with_decimal_progress", 1000),
    ],
)
async def test_update_with_progress(
    hass: HomeAssistant, entity_id: str, steps: int
) -> None:
    """Test update with progress."""
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    events = []
    async_track_state_change_event(
        hass,
        entity_id,
        # pylint: disable-next=unnecessary-lambda
        callback(lambda event: events.append(event)),
    )

    with patch("homeassistant.components.demo.update.FAKE_INSTALL_SLEEP_TIME", new=0):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert len(events) == steps + 1
    for i, event in enumerate(events[:steps]):
        new_state = event.data["new_state"]
        assert new_state.state == STATE_ON
        assert new_state.attributes[ATTR_UPDATE_PERCENTAGE] == pytest.approx(
            100 / steps * i
        )
    new_state = events[steps].data["new_state"]
    assert new_state.attributes[ATTR_IN_PROGRESS] is False
    assert new_state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert new_state.state == STATE_OFF


@pytest.mark.parametrize(
    ("entity_id", "steps"),
    [
        ("update.demo_update_with_progress", 10),
        ("update.demo_update_with_decimal_progress", 1000),
    ],
)
async def test_update_with_progress_raising(
    hass: HomeAssistant, entity_id: str, steps: int
) -> None:
    """Test update with progress failing to install."""
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    events = []
    async_track_state_change_event(
        hass,
        entity_id,
        # pylint: disable-next=unnecessary-lambda
        callback(lambda event: events.append(event)),
    )

    with (
        patch(
            "homeassistant.components.demo.update._fake_install",
            side_effect=[None, None, None, None, RuntimeError],
        ) as fake_sleep,
        pytest.raises(RuntimeError),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert fake_sleep.call_count == 5
    assert len(events) == 6
    for i, event in enumerate(events[:5]):
        new_state = event.data["new_state"]
        assert new_state.state == STATE_ON
        assert new_state.attributes[ATTR_UPDATE_PERCENTAGE] == pytest.approx(
            100 / steps * i
        )
    assert events[5].data["new_state"].attributes[ATTR_IN_PROGRESS] is False
    assert events[5].data["new_state"].attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert events[5].data["new_state"].state == STATE_ON
