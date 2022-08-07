"""The camera tests for the prosegur platform."""
from unittest.mock import AsyncMock, patch

from pyprosegur.installation import Camera

from homeassistant.components import camera
from homeassistant.components.camera import Image
from homeassistant.components.prosegur.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID

from .common import setup_platform


async def test_camera(hass, mock_prosegur_auth):
    """Test prosegur get_image."""

    install = AsyncMock()
    install.contract = "123"
    install.installationId = "1234abcd"
    install.cameras = [Camera("1", "test_cam")]
    install.get_image = AsyncMock(return_value=b"ABC")

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):

        await setup_platform(hass)

        await hass.async_block_till_done()

        image = await camera.async_get_image(hass, "camera.test_cam")

        assert image == Image(content_type="image/jpeg", content=b"ABC")


async def test_request_image(hass, mock_prosegur_auth):
    """Test the camera request image service."""

    install = AsyncMock()
    install.contract = "123"
    install.installationId = "1234abcd"
    install.cameras = [Camera("1", "test_cam")]
    install.request_image = AsyncMock()

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):

        await setup_platform(hass)

        await hass.services.async_call(
            DOMAIN,
            "request_image",
            {ATTR_ENTITY_ID: "camera.test_cam"},
        )
        await hass.async_block_till_done()

        assert install.request_image.called
