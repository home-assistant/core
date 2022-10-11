"""Basic checks for HomeKit cameras."""
import base64

from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FAKE_CAMERA_IMAGE

from homeassistant.components import camera
from homeassistant.helpers import entity_registry as er

from .common import setup_test_component


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


async def test_migrate_entity_ids(hass, utcnow):
    """Test migrating entity ids."""
    entity_registry = er.async_get(hass)
    camera = entity_registry.async_get_or_create(
        "camera",
        "homekit_controller",
        "homekit-0001-aid:3",
    )
    await setup_test_component(hass, create_camera)
    assert (
        entity_registry.async_get(camera.entity_id).unique_id == "00:00:00:00:00:00_3"
    )
