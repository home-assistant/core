"""Tests for the Clarifai component."""
from homeassistant.components.clarifai.api import Clarifai
from homeassistant.components.clarifai.const import (
    ATTR_APP_ID,
    ATTR_WORKFLOW_ID,
    DOMAIN as CLARIFAI_DOMAIN,
    EVENT_PREDICTION,
    SERVICE_PREDICT,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACCESS_TOKEN
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant

ENTITY_CAMERA = "camera.demo_camera"


class TestClarifaiSetup:
    """Test the Clarifai component."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {CLARIFAI_DOMAIN: {CONF_ACCESS_TOKEN: "12345678abcdef"}}

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_setup_component(self, mock_list):
        """Set up component."""
        with assert_setup_component(1, CLARIFAI_DOMAIN):
            setup_component(self.hass, CLARIFAI_DOMAIN, self.config)

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_setup_component_wrong_api_key(self, mock_list):
        """Set up component without api key."""
        with assert_setup_component(0, CLARIFAI_DOMAIN):
            setup_component(self.hass, CLARIFAI_DOMAIN, {CLARIFAI_DOMAIN: {}})

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_setup_component_test_services(self, mock_list):
        """Set up component and test for services."""
        with assert_setup_component(1, CLARIFAI_DOMAIN):
            setup_component(self.hass, CLARIFAI_DOMAIN, self.config)
            self.hass.block_till_done()

        assert self.hass.services.has_service(CLARIFAI_DOMAIN, SERVICE_PREDICT)

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_service_predict(self, mock_list):
        """Set up component with camera and test predict service."""
        self.config["camera"] = {"platform": "demo"}
        with assert_setup_component(1, CLARIFAI_DOMAIN):
            setup_component(self.hass, CLARIFAI_DOMAIN, self.config)
            self.hass.block_till_done()

        prediction_events = []
        self.hass.bus.listen(EVENT_PREDICTION, prediction_events.append)

        app_id = "12345678abcdef"
        workflow_id = "Face"

        data = {
            ATTR_APP_ID: app_id,
            ATTR_WORKFLOW_ID: workflow_id,
            ATTR_ENTITY_ID: ENTITY_CAMERA,
        }

        with patch.object(
            Clarifai, "post_workflow_results", return_value=None
        ) as mock_post_workflow_results:
            self.hass.services.call(CLARIFAI_DOMAIN, SERVICE_PREDICT, data)
            self.hass.block_till_done()

        mock_post_workflow_results.assert_called_once()
        assert (len(prediction_events)) == 1
