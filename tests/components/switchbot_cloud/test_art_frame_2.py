"""Test AI Art Frame 2 cloud support."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import (
    async_load_json_object_fixture,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.image import async_get_image
from homeassistant.components.switchbot_cloud.const import (
    AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_WEBHOOK_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import configure_integration


@pytest.fixture
async def art_frame_2(
    hass: HomeAssistant,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    mock_get_webook_configuration: AsyncMock,
) -> None:
    """Return the documented Art Frame 2 device and status."""
    await async_process_ha_core_config(hass, {"external_url": "https://example.com"})
    mock_list_devices.return_value = [
        Device(
            deviceId="B0E9FEC395F0",
            deviceName="Art Frame 2",
            deviceType="AI Art Frame 2",
            enableCloudService=True,
            hubDeviceId="",
        )
    ]
    mock_get_status.return_value = await async_load_json_object_fixture(
        hass, "art_frame_2_status.json", DOMAIN
    )
    mock_get_webook_configuration.return_value = {"urls": []}


@pytest.mark.usefixtures(
    "art_frame_2", "mock_setup_webhook", "mock_delete_webhook", "freezer"
)
@pytest.mark.freeze_time("2026-11-13T00:00:00+00:00")
@pytest.mark.parametrize("platform", [Platform.SENSOR, Platform.IMAGE, Platform.BUTTON])
async def test_art_frame_2_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Create the battery, display, and navigation entities."""
    with (
        patch("homeassistant.components.switchbot_cloud.PLATFORMS", [platform]),
        patch("homeassistant.components.image.entity._RND.getrandbits", return_value=0),
    ):
        entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("art_frame_2", "mock_setup_webhook", "mock_delete_webhook")
@pytest.mark.parametrize("command", ["previous", "next"])
async def test_art_frame_2_navigation(hass: HomeAssistant, command: str) -> None:
    """Send navigation commands to the new frame."""
    entry = await configure_integration(hass)
    with patch.object(entry.runtime_data.api, "send_command") as mock_send:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: f"button.art_frame_2_{command}"},
            blocking=True,
        )
    mock_send.assert_awaited_once_with("B0E9FEC395F0", command, "command", "default")


@pytest.mark.usefixtures("art_frame_2", "mock_setup_webhook", "mock_delete_webhook")
async def test_art_frame_2_upload(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Upload an image through the existing action."""
    entry = await configure_integration(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "B0E9FEC395F0"), entry.entry_id
    )
    with patch.object(entry.runtime_data.api, "send_command") as mock_send:
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": device.id, "image_url": "https://example.com/new.jpg"},
            blocking=True,
        )
    mock_send.assert_awaited_once_with(
        device_id="B0E9FEC395F0",
        command="uploadImage",
        command_type="command",
        parameters={"imageUrl": "https://example.com/new.jpg"},
    )


@pytest.mark.usefixtures("art_frame_2", "mock_setup_webhook", "mock_delete_webhook")
async def test_art_frame_2_webhook_keeps_image(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Update battery without clearing the image on a display-mode webhook."""
    entry = await configure_integration(hass)
    image_state = hass.states.get("image.art_frame_2_display").state
    assert image_state != STATE_UNKNOWN
    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{entry.data[CONF_WEBHOOK_ID]}",
        json={
            "eventType": "changeReport",
            "eventVersion": "1",
            "context": {
                "deviceType": "AI Art Frame 2",
                "deviceMac": "B0E9FEC395F0",
                "displayMode": 1,
                "battery": 100,
                "timeOfSample": 123456789,
            },
        },
    )
    assert response.status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.art_frame_2_battery").state == "100"
    assert hass.states.get("image.art_frame_2_display").state == image_state
    with patch(
        "homeassistant.components.switchbot_cloud.image.get_file_stream_from_cloud",
        return_value=b"image bytes",
    ) as mock_download:
        image = await async_get_image(hass, "image.art_frame_2_display")
    assert image.content == b"image bytes"
    mock_download.assert_awaited_once_with("https://example.com/art-frame-2.jpg", 5)
