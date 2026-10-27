"""Test the Reolink camera platform."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from reolink_aio.exceptions import ReolinkError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraState,
    async_get_image,
    async_get_stream_source,
    async_register_webrtc_provider,
)
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import TEST_CAM_NAME, TEST_DUO_MODEL, TEST_NVR_NAME

from tests.components.camera.common import SomeTestProvider


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "reolink_host")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with (
        patch(
            "homeassistant.components.reolink.PLATFORMS",
            [Platform.CAMERA],
        ),
        # keep the camera access tokens deterministic for the snapshot
        patch("random.SystemRandom.getrandbits", return_value=123123123123),
    ):
        await setup_integration(hass, config_entry)
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_camera(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test camera entity with fluent."""

    def mock_supported(ch, capability):
        if capability == "ext_stream":
            return False
        return True

    reolink_host.supported = mock_supported

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.CAMERA}.{TEST_CAM_NAME}_fluent"
    assert hass.states.get(entity_id).state == CameraState.IDLE

    # check getting a image from the camera
    reolink_host.get_snapshot.return_value = b"image"
    assert (await async_get_image(hass, entity_id)).content == b"image"

    reolink_host.get_snapshot.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, entity_id)

    # check getting the stream source
    assert await async_get_stream_source(hass, entity_id) is not None


@pytest.mark.parametrize(
    ("protocol", "two_way_audio_supported", "expected_two_way_audio"),
    [
        pytest.param("rtsp", True, True, id="supported"),
        pytest.param("rtsp", False, False, id="not_supported"),
        pytest.param("rtmp", True, False, id="not_rtsp"),
    ],
)
async def test_camera_two_way_audio(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    protocol: str,
    two_way_audio_supported: bool,
    expected_two_way_audio: bool,
) -> None:
    """Test two way audio capability of the camera entity."""
    reolink_host.protocol = protocol
    reolink_host.supported.side_effect = lambda ch, capability: {
        "ext_stream": False,
        "two_way_audio": two_way_audio_supported,
    }.get(capability, True)

    # Two way audio is only offered over WebRTC with the labs feature enabled
    assert await async_setup_component(hass, "labs", {})
    assert await async_setup_component(hass, CAMERA_DOMAIN, {})
    await async_update_preview_feature(hass, CAMERA_DOMAIN, "two_way_audio", True)
    async_register_webrtc_provider(hass, SomeTestProvider())

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/capabilities",
            "entity_id": f"{Platform.CAMERA}.{TEST_CAM_NAME}_fluent",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["two_way_audio"] is expected_two_way_audio


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_no_stream_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test camera entity with no stream source."""
    reolink_host.model = TEST_DUO_MODEL
    reolink_host.get_stream_source.return_value = None

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.CAMERA}.{TEST_NVR_NAME}_lens_0_snapshots_fluent"
    assert hass.states.get(entity_id).state == CameraState.IDLE
