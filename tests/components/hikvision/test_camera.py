"""Test Hikvision cameras."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import entity_callbacks, setup_integration
from .conftest import TEST_DEVICE_ID, TEST_DEVICE_NAME, TEST_HOST


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.CAMERA]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all camera entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("amount_of_channels", [2])
async def test_nvr_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test NVR camera entities with multiple channels."""
    mock_hikcamera.return_value.get_type = "NVR"

    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("amount_of_channels", [2])
async def test_nvr_entities_with_channel_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test NVR camera entities use custom channel names when available."""
    mock_hikcamera.return_value.get_type = "NVR"

    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    # Verify device names use channel names instead of "Channel N"
    device_1 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_DEVICE_ID}_1"), mock_config_entry.entry_id
    )
    assert device_1 is not None
    assert device_1.name == "Front Camera channel 1"

    device_2 = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_DEVICE_ID}_2"), mock_config_entry.entry_id
    )
    assert device_2 is not None
    assert device_2.name == "Front Camera channel 2"


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test camera is linked to device."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.name == TEST_DEVICE_NAME
    assert device_entry.manufacturer == "Hikvision"
    assert device_entry.model == "Camera"


async def test_camera_no_channels_creates_single_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera created when device returns no channels."""
    mock_hikcamera.return_value.get_channels.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Single camera should be created for channel 1
    states = hass.states.async_entity_ids("camera")
    assert len(states) == 1

    state = hass.states.get("camera.front_camera")
    assert state is not None


async def test_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test getting camera image."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, "camera.front_camera")
    assert image.content == b"fake_image_data"

    # Verify get_snapshot was called with channel 1
    mock_hikcamera.return_value.get_snapshot.assert_called_with(1)


async def test_camera_image_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera image error handling."""
    mock_hikcamera.return_value.get_snapshot.side_effect = Exception("Connection error")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="Error getting image"):
        await async_get_image(hass, "camera.front_camera")


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera stream source URL."""
    await setup_integration(hass, mock_config_entry)

    stream_url = await async_get_stream_source(hass, "camera.front_camera")

    # Verify RTSP URL from library
    assert stream_url is not None
    assert stream_url.startswith("rtsp://")
    assert f"@{TEST_HOST}:554/Streaming/Channels/1" in stream_url

    # Verify get_stream_url was called with channel 1
    mock_hikcamera.return_value.get_stream_url.assert_called_with(1, stream_type=1)


async def test_substream_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the substream camera is created but disabled by default."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get_entity_id(
        "camera", DOMAIN, f"{TEST_DEVICE_ID}_1_substream"
    )
    assert entry is not None
    assert (
        entity_registry.async_get(entry).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(entry) is None
    # The main stream keeps its original unique ID and stays enabled
    assert hass.states.get("camera.front_camera") is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_substream_stream_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the substream camera requests the substream URL."""
    camera = mock_hikcamera.return_value
    camera.get_stream_url.side_effect = lambda channel, stream_type=1: (
        f"rtsp://u:p@{TEST_HOST}:554/Streaming/Channels/{stream_type}"
    )
    await setup_integration(hass, mock_config_entry)

    stream_url = await async_get_stream_source(hass, "camera.front_camera_substream")

    assert stream_url is not None
    assert stream_url.endswith("/Streaming/Channels/2")
    camera.get_stream_url.assert_called_with(1, stream_type=2)


async def test_camera_unavailable_when_stream_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the camera goes unavailable when the event stream disconnects."""
    camera = mock_hikcamera.return_value
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_camera")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # pyhik notifies every registered callback when the stream drops
    camera.stream_connected = False
    callback_func = entity_callbacks(camera)[0]
    callback_func("stream disconnected")
    await hass.async_block_till_done()

    state = hass.states.get("camera.front_camera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_camera_callback_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the pyhik callback is unregistered when the entity is removed."""
    camera = mock_hikcamera.return_value
    await setup_integration(hass, mock_config_entry)

    added = [
        c.args
        for c in camera.add_update_callback.call_args_list
        if c.args[1] == f"{TEST_DEVICE_ID}.camera.1"
    ]
    assert len(added) == 1
    camera.remove_update_callback.assert_not_called()

    entity_registry.async_remove("camera.front_camera")
    await hass.async_block_till_done()

    camera.remove_update_callback.assert_called_once_with(*added[0])
