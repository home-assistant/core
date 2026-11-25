"""Basic checks for HomeKit cameras."""

import base64
from collections.abc import Callable
from unittest.mock import ANY, patch

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FAKE_CAMERA_IMAGE
import pytest

from homeassistant.components import camera
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import setup_test_component

# Supported Video Stream Configuration of an Aqara G410 doorbell: H.264 at
# 1600x1200, 1280x960, 640x480, 480x360 and 320x240
G410_VIDEO_CONFIGURATION = (
    "AVwBAQACDgEBAQIBAAAAAgECAwEAAwsBAkAGAgKwBAMBHgAAAwsBAgAFAgLAAwMBHgAAAwsBAoAC"
    "AgLgAQMBHgAAAwsBAuABAgJoAQMBHgAAAwsBAkABAgLwAAMBHg=="
)


def create_camera(accessory: Accessory) -> None:
    """Define camera characteristics."""
    accessory.add_service(ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT)


def create_camera_with_sizes(accessory: Accessory) -> None:
    """Define a camera that lists the sizes of its video streams."""
    service = accessory.add_service(ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT)
    configuration = service.add_char(
        CharacteristicsTypes.SUPPORTED_VIDEO_STREAM_CONFIGURATION
    )
    configuration.value = G410_VIDEO_CONFIGURATION
    # Read it as an accessory sends it, not decoded as the fake pairing would
    configuration.get_value = lambda: G410_VIDEO_CONFIGURATION


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


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        # Card sizes on a dashboard: the smallest listed size covering them
        ((534, 301), (640, 480)),
        ((267, 150), (320, 240)),
        # A listed size is passed through
        ((480, 360), (480, 360)),
        # Larger than any listed size: the largest
        ((3000, 2000), (1600, 1200)),
        # No size: the default, which is listed
        ((None, None), (640, 480)),
    ],
)
async def test_get_image_listed_size(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
    requested: tuple[int | None, int | None],
    expected: tuple[int, int],
) -> None:
    """Test a size the camera lists is requested.

    Some cameras never answer a size they don't list, so the request times out.
    """
    helper = await setup_test_component(hass, get_next_aid(), create_camera_with_sizes)

    with patch.object(
        helper.pairing, "image", return_value=base64.b64decode(FAKE_CAMERA_IMAGE)
    ) as mock_image:
        image = await camera.async_get_image(
            hass, helper.entity_id, width=requested[0], height=requested[1]
        )

    assert image.content
    mock_image.assert_awaited_once_with(ANY, *expected)


async def test_get_image_listed_size_rejected_falls_back_to_default(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test falling back to the default size when a listed size is rejected."""
    helper = await setup_test_component(hass, get_next_aid(), create_camera_with_sizes)

    async def _image(aid: int, width: int, height: int) -> bytes | None:
        """Mimic a G410, which lists 1280x960 but rejects it for snapshots."""
        if (width, height) == (1280, 960):
            return None
        return base64.b64decode(FAKE_CAMERA_IMAGE)

    with patch.object(helper.pairing, "image", side_effect=_image) as mock_image:
        image = await camera.async_get_image(
            hass, helper.entity_id, width=1000, height=750
        )

    assert image.content
    assert [call.args[1:] for call in mock_image.await_args_list] == [
        (1280, 960),
        (640, 480),
    ]
