"""Tests for the Clarifai component."""
from homeassistant.components import clarifai
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant


class TestClarifaiSetup:
    """Test the Clarifai component."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {clarifai.DOMAIN: {CONF_ACCESS_TOKEN: "12345678abcdef"}}

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_setup_component(self, mock_update):
        """Set up component."""
        with assert_setup_component(1, clarifai.DOMAIN):
            setup_component(self.hass, clarifai.DOMAIN, self.config)

    @patch(
        "homeassistant.components.clarifai.api.Clarifai.list_apps", return_value=None,
    )
    def test_setup_component_wrong_api_key(self, mock_update):
        """Set up component without api key."""
        with assert_setup_component(0, clarifai.DOMAIN):
            setup_component(self.hass, clarifai.DOMAIN, {clarifai.DOMAIN: {}})
