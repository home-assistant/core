"""Tests for the Clarifai image processing platform."""
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.clarifai.const import (
    CONF_APP_ID,
    CONF_WORKFLOW_ID,
    DOMAIN as CLARIFAI_DOMAIN,
)
from homeassistant.components.demo import DOMAIN as DEMO_DOMAIN
from homeassistant.components.image_processing import DOMAIN as IP_DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_SOURCE,
)
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant

ENTITY_CAMERA = "camera.demo_camera"


class TestClarifaiImageProcessing:
    """Test class for image processing."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {CLARIFAI_DOMAIN: {CONF_ACCESS_TOKEN: "12345678abcdef"}}

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.verify_access",
        return_value=None,
    )
    def test_setup_platform(self, mock_access):
        """Set up platform with one entity."""
        self.config[IP_DOMAIN] = {
            CONF_PLATFORM: CLARIFAI_DOMAIN,
            CONF_SOURCE: {CONF_ENTITY_ID: ENTITY_CAMERA},
            CONF_APP_ID: "12345678abcdef",
            CONF_WORKFLOW_ID: "Face",
        }

        self.config[CAMERA_DOMAIN] = {
            CONF_PLATFORM: DEMO_DOMAIN,
        }

        with assert_setup_component(1, IP_DOMAIN):
            setup_component(self.hass, IP_DOMAIN, self.config)
            self.hass.block_till_done()

        assert self.hass.states.get("image_processing.clarifai_demo_camera")

    # def test_setup_platform_no_camera(self, mock_access):

    # def test_setup_platform_multiple_cameras(self, mock_access):

    # def test_process_image(self, mock_access):
