"""Basic checks for HomeKit cameras."""
import base64

from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FAKE_CAMERA_IMAGE

from homeassistant.components import camera

from tests.components.homekit_controller.common import setup_test_component


def create_camera(accessory):
    """Define camera characteristics."""
    accessory.add_service(ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT)


async def test_read_state(hass, utcnow):
    """Test reading the state of a HomeKit camera."""
    helper = await setup_test_component(hass, create_camera)

    state = await helper.poll_and_get_state()
    assert state.state == "idle"


async def test_get_image(hass, utcnow):
    """Test getting a JPEG from a camera."""
    helper = await setup_test_component(hass, create_camera)
    image = await camera.async_get_image(hass, helper.entity_id)
    assert image.content == base64.b64decode(FAKE_CAMERA_IMAGE)
