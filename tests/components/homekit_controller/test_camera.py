"""Basic checks for HomeKit cameras."""

import asyncio
import base64
from collections.abc import Callable
from unittest.mock import ANY, Mock, patch

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FAKE_CAMERA_IMAGE
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import camera
from homeassistant.components.camera import (
    CameraEntityFeature,
    get_camera_from_entity_id,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import TEST_IP_PAIRING_DATA, Helper, setup_test_component


def create_camera(accessory: Accessory) -> None:
    """Define camera characteristics."""
    accessory.add_service(ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT)


def create_doorbell_camera(accessory: Accessory) -> None:
    """Define a camera with a speaker for talk-back."""
    create_camera(accessory)
    speaker = accessory.add_service(ServicesTypes.SPEAKER)
    speaker.add_char(CharacteristicsTypes.MUTE, value=False)


async def test_migrate_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test migrating entity unique ids."""
    aid = get_next_aid()
    camera = entity_registry.async_get_or_create(
        "camera",
        "homekit_controller",
        f"homekit-0001-aid:{aid}",
    )
    await setup_test_component(hass, aid, create_camera)
    assert (
        entity_registry.async_get(camera.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}"
    )


async def test_read_state(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test reading the state of a HomeKit camera."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    state = await helper.poll_and_get_state()
    assert state.state == "idle"


async def test_get_image(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test getting a JPEG from a camera."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)
    image = await camera.async_get_image(hass, helper.entity_id)
    assert image.content == base64.b64decode(FAKE_CAMERA_IMAGE)


async def test_get_image_default_size(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test the default size is requested when none is given."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    with patch.object(
        helper.pairing, "image", return_value=base64.b64decode(FAKE_CAMERA_IMAGE)
    ) as mock_image:
        image = await camera.async_get_image(hass, helper.entity_id)

    assert image.content == base64.b64decode(FAKE_CAMERA_IMAGE)
    mock_image.assert_awaited_once_with(ANY, 640, 480)


async def test_get_image_requested_size_supported(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test a supported requested size is passed to the accessory unchanged."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    with patch.object(
        helper.pairing, "image", return_value=base64.b64decode(FAKE_CAMERA_IMAGE)
    ) as mock_image:
        image = await camera.async_get_image(
            hass, helper.entity_id, width=320, height=240
        )

    assert image.content
    mock_image.assert_awaited_once_with(ANY, 320, 240)


async def test_get_image_unsupported_size_falls_back_to_default(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test falling back to the default size when the accessory rejects a size."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    async def _image(aid: int, width: int, height: int) -> bytes | None:
        """Mimic an accessory that only serves 640x480.

        aiohomekit returns None when the accessory answers with an HTTP error.
        """
        if (width, height) != (640, 480):
            return None
        return base64.b64decode(FAKE_CAMERA_IMAGE)

    with patch.object(helper.pairing, "image", side_effect=_image) as mock_image:
        image = await camera.async_get_image(
            hass, helper.entity_id, width=500, height=375
        )

    assert image.content
    assert [call.args[1:] for call in mock_image.await_args_list] == [
        (500, 375),
        (640, 480),
    ]


async def test_get_image_fails_when_default_size_also_fails(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test the error is still raised if the fallback does not return an image."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    with (
        patch.object(helper.pairing, "image", return_value=None) as mock_image,
        pytest.raises(HomeAssistantError, match="Unable to get image"),
    ):
        await camera.async_get_image(hass, helper.entity_id, width=500, height=375)

    assert [call.args[1:] for call in mock_image.await_args_list] == [
        (500, 375),
        (640, 480),
    ]


async def test_get_image_default_size_failure_is_not_retried(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test a failure at the default size is not retried."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera)

    with (
        patch.object(helper.pairing, "image", return_value=None) as mock_image,
        pytest.raises(HomeAssistantError, match="Unable to get image"),
    ):
        await camera.async_get_image(hass, helper.entity_id)

    mock_image.assert_awaited_once_with(ANY, 640, 480)


async def test_webrtc_source(hass: HomeAssistant) -> None:
    """Test an IP camera exposes its live stream as a go2rtc homekit:// source."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")

    state = await helper.poll_and_get_state()
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == CameraEntityFeature.STREAM
    # FFmpeg can't open homekit://, so there is no stream source
    assert await camera.async_get_stream_source(hass, helper.entity_id) is None
    assert await camera.get_camera_from_entity_id(
        hass, helper.entity_id
    ).webrtc_source() == (
        "homekit://192.168.1.50:51826/"
        "?device_id=00:00:00:00:00:00"
        f"&device_public={TEST_IP_PAIRING_DATA['AccessoryLTPK']}"
        "&client_id=00000000-0000-0000-0000-000000000000"
        f"&client_private={TEST_IP_PAIRING_DATA['iOSDeviceLTSK']}"
        f"{TEST_IP_PAIRING_DATA['iOSDeviceLTPK']}"
    )


async def test_snapshots_only_without_webrtc_provider(hass: HomeAssistant) -> None:
    """Test a camera without a WebRTC provider keeps the MJPEG fallback."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")

    entity = get_camera_from_entity_id(hass, helper.entity_id)
    assert entity.webrtc_provider is None
    # No HLS, as FFmpeg can't open homekit://, so media players get MJPEG
    assert entity.camera_capabilities.frontend_stream_types == set()


@pytest.mark.parametrize(
    ("address", "port", "authority"),
    [
        pytest.param("192.168.1.60", 51827, "192.168.1.60:51827", id="ipv4"),
        pytest.param("fd00::60", 51827, "[fd00::60]:51827", id="ipv6"),
    ],
)
async def test_webrtc_source_follows_address_change(
    hass: HomeAssistant, address: str, port: int, authority: str
) -> None:
    """Test the WebRTC source uses the address discovery last stored."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")

    hass.config_entries.async_update_entry(
        helper.config_entry,
        data={
            **helper.config_entry.data,
            "AccessoryIP": address,
            "AccessoryPort": port,
        },
    )

    source = await camera.get_camera_from_entity_id(
        hass, helper.entity_id
    ).webrtc_source()
    assert source == (
        f"homekit://{authority}/"
        "?device_id=00:00:00:00:00:00"
        f"&device_public={TEST_IP_PAIRING_DATA['AccessoryLTPK']}"
        "&client_id=00000000-0000-0000-0000-000000000000"
        f"&client_private={TEST_IP_PAIRING_DATA['iOSDeviceLTSK']}"
        f"{TEST_IP_PAIRING_DATA['iOSDeviceLTPK']}"
    )


async def _move_camera(hass: HomeAssistant, helper: Helper, address: str) -> None:
    """Store a new address for the camera, as discovery does."""
    hass.config_entries.async_update_entry(
        helper.config_entry,
        data={**helper.config_entry.data, "AccessoryIP": address},
    )
    await hass.async_block_till_done()


async def test_stream_follows_address_change(hass: HomeAssistant) -> None:
    """Test a running stream gets the new address, as HLS keeps reading it."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")
    entity = get_camera_from_entity_id(hass, helper.entity_id)
    entity.stream = Mock()

    with patch.object(entity, "async_create_stream") as create_stream:
        # Another update leaves the address, so the stream, alone
        hass.config_entries.async_update_entry(
            helper.config_entry, data={**helper.config_entry.data, "Other": 1}
        )
        await hass.async_block_till_done()
        create_stream.assert_not_called()

        await _move_camera(hass, helper, "192.168.1.60")

    create_stream.assert_awaited_once()


async def test_stream_address_update_retried(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed address update is retried until go2rtc has it.

    The error isn't logged, as it can carry the pairing key.
    """
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")
    entity = get_camera_from_entity_id(hass, helper.entity_id)
    entity.stream = Mock()

    with patch.object(
        entity,
        "async_create_stream",
        side_effect=[HomeAssistantError("secret"), TimeoutError, None],
    ) as create_stream:
        await _move_camera(hass, helper, "192.168.1.60")
        assert create_stream.await_count == 1
        for delay in (5, 15):
            freezer.tick(delay)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        assert create_stream.await_count == 3

        # Updated, so no further retries
        freezer.tick(300)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert create_stream.await_count == 3

    assert caplog.text.count("Unable to update the stream") == 1
    assert f"Updated the stream of {helper.entity_id}" in caplog.text
    assert "secret" not in caplog.text


async def test_stream_address_update_waits_for_stream_creation(
    hass: HomeAssistant,
) -> None:
    """Test an address change during stream creation updates the new stream."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")
    entity = get_camera_from_entity_id(hass, helper.entity_id)
    entity._create_stream_lock = asyncio.Lock()

    with patch.object(entity, "async_create_stream") as create_stream:
        async with entity._create_stream_lock:
            hass.config_entries.async_update_entry(
                helper.config_entry,
                data={**helper.config_entry.data, "AccessoryIP": "192.168.1.60"},
            )
            for _ in range(5):
                await asyncio.sleep(0)
            # The stream being created resolved the old address
            entity.stream = Mock()
        await hass.async_block_till_done()

    create_stream.assert_awaited_once()


async def test_stream_address_retry_stopped_on_removal(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a pending address update retry is cancelled with the entity."""
    helper = await setup_test_component(hass, 1, create_camera, connection="IP")
    entity = get_camera_from_entity_id(hass, helper.entity_id)
    entity.stream = Mock()

    with patch.object(
        entity, "async_create_stream", side_effect=HomeAssistantError
    ) as create_stream:
        await _move_camera(hass, helper, "192.168.1.60")
        await hass.config_entries.async_unload(helper.config_entry.entry_id)
        freezer.tick(300)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    create_stream.assert_awaited_once()


async def test_no_stream_for_bridged_camera(hass: HomeAssistant) -> None:
    """Test a camera behind a bridge does not offer a live stream."""
    helper = await setup_test_component(hass, 2, create_camera, connection="IP")

    state = await helper.poll_and_get_state()
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert (
        await camera.get_camera_from_entity_id(hass, helper.entity_id).webrtc_source()
        is None
    )


@pytest.mark.usefixtures("enable_bluetooth", "fake_ble_discovery", "fake_ble_pairing")
async def test_no_stream_for_ble_camera(hass: HomeAssistant) -> None:
    """Test a camera not paired over IP does not offer a live stream."""
    helper = await setup_test_component(hass, 1, create_camera, connection="BLE")

    state = await helper.poll_and_get_state()
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert (
        await camera.get_camera_from_entity_id(hass, helper.entity_id).webrtc_source()
        is None
    )


@pytest.mark.parametrize(
    ("create", "two_way_audio"),
    [
        pytest.param(create_doorbell_camera, True, id="speaker"),
        pytest.param(create_camera, False, id="no_speaker"),
    ],
)
async def test_two_way_audio(
    hass: HomeAssistant,
    create: Callable[[Accessory], None],
    two_way_audio: bool,
) -> None:
    """Test streaming cameras with a speaker declare two way audio."""
    helper = await setup_test_component(hass, 1, create, connection="IP")

    entity = get_camera_from_entity_id(hass, helper.entity_id)
    assert entity.camera_entity_capabilities.two_way_audio is two_way_audio


async def test_no_two_way_audio_without_stream(hass: HomeAssistant) -> None:
    """Test a camera that can't stream doesn't declare two way audio."""
    helper = await setup_test_component(
        hass, 2, create_doorbell_camera, connection="IP"
    )

    entity = get_camera_from_entity_id(hass, helper.entity_id)
    assert entity.camera_entity_capabilities.two_way_audio is False
