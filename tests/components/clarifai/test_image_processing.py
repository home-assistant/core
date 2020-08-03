"""Tests for the Clarifai image processing platform."""
from clarifai_grpc.grpc.api import service_pb2
from google.protobuf.json_format import Parse

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.clarifai.api import Clarifai
from homeassistant.components.clarifai.const import (
    CONF_APP_ID,
    CONF_WORKFLOW_ID,
    DOMAIN as CLARIFAI_DOMAIN,
    EVENT_PREDICTION,
)
from homeassistant.components.demo import DOMAIN as DEMO_DOMAIN
from homeassistant.components.image_processing import DOMAIN as IP_DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SOURCE,
)
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant, load_fixture
from tests.components.image_processing import common


class TestClarifaiImageProcessingSetup:
    """Test class for image processing setup."""

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
            CONF_APP_ID: "12345678abcdef",
            CONF_WORKFLOW_ID: "Face",
            CONF_SOURCE: {CONF_ENTITY_ID: "camera.demo_camera"},
        }

        self.config[CAMERA_DOMAIN] = {
            CONF_PLATFORM: DEMO_DOMAIN,
        }

        with assert_setup_component(1, IP_DOMAIN):
            setup_component(self.hass, IP_DOMAIN, self.config)
            self.hass.block_till_done()

        assert self.hass.states.get("camera.demo_camera")
        assert self.hass.states.get("image_processing.clarifai_demo_camera")

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.verify_access",
        return_value=None,
    )
    def test_setup_platform_name(self, mock_access):
        """Set up platform with one entity and name."""
        self.config[IP_DOMAIN] = {
            CONF_PLATFORM: CLARIFAI_DOMAIN,
            CONF_APP_ID: "12345678abcdef",
            CONF_WORKFLOW_ID: "Face",
            CONF_SOURCE: {
                CONF_ENTITY_ID: "camera.demo_camera",
                CONF_NAME: "test local",
            },
        }

        self.config[CAMERA_DOMAIN] = {
            CONF_PLATFORM: DEMO_DOMAIN,
        }

        with assert_setup_component(1, IP_DOMAIN):
            setup_component(self.hass, IP_DOMAIN, self.config)
            self.hass.block_till_done()

        assert self.hass.states.get("image_processing.test_local")

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.verify_access",
        return_value=None,
    )
    def test_setup_platform_multiple_cameras(self, mock_access):
        """Set up platform with multiple cameras."""
        self.config[IP_DOMAIN] = {
            CONF_PLATFORM: CLARIFAI_DOMAIN,
            CONF_APP_ID: "12345678abcdef",
            CONF_WORKFLOW_ID: "Face",
            CONF_SOURCE: [
                {CONF_ENTITY_ID: "camera.foo"},
                {CONF_ENTITY_ID: "camera.bar"},
            ],
        }

        self.config[CAMERA_DOMAIN] = [
            {CONF_PLATFORM: DEMO_DOMAIN, CONF_NAME: "foo"},
            {CONF_PLATFORM: DEMO_DOMAIN, CONF_NAME: "bar"},
        ]

        with assert_setup_component(1, IP_DOMAIN):
            setup_component(self.hass, IP_DOMAIN, self.config)
            self.hass.block_till_done()

        assert self.hass.states.get("image_processing.clarifai_foo")
        assert self.hass.states.get("image_processing.clarifai_bar")

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.verify_access",
        return_value=None,
    )
    def test_setup_platform_no_camera(self, mock_access):
        """Set up platform with no camera."""
        self.config[IP_DOMAIN] = {
            CONF_PLATFORM: CLARIFAI_DOMAIN,
            CONF_APP_ID: "12345678abcdef",
            CONF_WORKFLOW_ID: "Face",
        }

        with assert_setup_component(0, IP_DOMAIN):
            setup_component(self.hass, IP_DOMAIN, self.config)


class TestClarifaiImageProcessing:
    """Test class for image processing with Clarifai."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            CLARIFAI_DOMAIN: {CONF_ACCESS_TOKEN: "12345678abcdef"},
            IP_DOMAIN: {
                CONF_PLATFORM: CLARIFAI_DOMAIN,
                CONF_APP_ID: "12345678abcdef",
                CONF_WORKFLOW_ID: "Face",
                CONF_SOURCE: {CONF_ENTITY_ID: "camera.demo_camera", CONF_NAME: "test"},
            },
            CAMERA_DOMAIN: {CONF_PLATFORM: DEMO_DOMAIN},
        }

        with patch(
            "homeassistant.components.clarifai.api.Clarifai.verify_access",
            return_value=None,
        ):
            setup_component(self.hass, IP_DOMAIN, self.config)
            self.hass.block_till_done()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_process_image(self):
        """Test process image method of image processing entity."""
        prediction_events = []
        self.hass.bus.listen(EVENT_PREDICTION, prediction_events.append)

        with patch.object(
            Clarifai, "post_workflow_results", return_value=None
        ) as mock_post_workflow_results:
            common.scan(self.hass, entity_id="image_processing.test")
            self.hass.block_till_done()

        mock_post_workflow_results.assert_called_once()
        assert len(prediction_events) == 1

    def test_process_image_error(self):
        """Test that process image catches error from failed response."""
        prediction_events = []
        self.hass.bus.listen(EVENT_PREDICTION, prediction_events.append)

        message = Parse(
            load_fixture("clarifai_response_failure.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        with patch.object(Clarifai, "post_workflow_results", return_value=message):
            common.scan(self.hass, entity_id="image_processing.test")

        assert len(prediction_events) == 0
