"""Test the logbook descriptions of Hikvision."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from pyhik.image import ImageWriteResult
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.hikvision.const import DOMAIN, EVENT_IMAGE_SETTING_CHANGED
from homeassistant.components.hikvision.logbook import async_describe_events
from homeassistant.components.recorder import Recorder
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import TEST_DEVICE_ID

HLC = "switch.front_camera_highlight_compensation"
SMART_LIGHT = "switch.front_camera_smart_supplement_light"
MESSAGE = (
    "was turned off automatically so that Front Camera Smart supplement light could"
    " be changed"
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SWITCH]


async def test_an_image_setting_change_is_described(hass: HomeAssistant) -> None:
    """Test the entry shows the name and the message, linked to its entity."""
    described: dict[tuple[str, str], Callable[[Event], dict[str, Any]]] = {}

    def _describe(
        domain: str, event_type: str, describe: Callable[[Event], dict[str, Any]]
    ) -> None:
        described[domain, event_type] = describe

    async_describe_events(hass, _describe)
    describe = described[DOMAIN, EVENT_IMAGE_SETTING_CHANGED]

    assert describe(
        Event(
            EVENT_IMAGE_SETTING_CHANGED,
            {
                "name": "Front Camera Highlight compensation",
                "message": "was turned off automatically",
                ATTR_ENTITY_ID: "switch.front_camera_highlight_compensation",
                ATTR_DEVICE_ID: "device",
            },
        )
    ) == {
        "name": "Front Camera Highlight compensation",
        "message": "was turned off automatically",
        "entity_id": "switch.front_camera_highlight_compensation",
    }
    assert describe(
        Event(
            EVENT_IMAGE_SETTING_CHANGED,
            {"name": "WDR/mode", "message": "was turned off automatically"},
        )
    ) == {"name": "WDR/mode", "message": "was turned off automatically"}


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_setting_changed_to_make_room_is_in_the_logbook(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the entry is recorded, and shown for its entity and for the camera."""
    start = dt_util.utcnow()
    assert await async_setup_component(hass, "logbook", {})
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        True, 200, "ok", {"HLC/enabled": "false"}
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SMART_LIGHT}, blocking=True
    )
    await async_wait_recording_done(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_ID), mock_config_entry.entry_id
    )
    client = await hass_ws_client()
    for query in ({"entity_ids": [HLC]}, {"device_ids": [device.id]}):
        await client.send_json_auto_id(
            {"type": "logbook/get_events", "start_time": start.isoformat(), **query}
        )
        response = await client.receive_json()
        assert response["success"]
        entries = [
            (entry["name"], entry.get("entity_id"), entry["domain"])
            for entry in response["result"]
            if entry.get("message") == MESSAGE
        ]
        assert entries == [("Front Camera Highlight compensation", HLC, DOMAIN)], query
