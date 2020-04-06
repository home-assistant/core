"""The tests for the image_processing component."""
from unittest.mock import PropertyMock, patch

import homeassistant.components.http as http
import homeassistant.components.image_processing as ip
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import setup_component

from tests.common import (
    assert_setup_component,
    get_test_home_assistant,
    get_test_instance_port,
)
from tests.components.image_processing import common


class TestSetupImageProcessing:
    """Test class for setup image processing."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Set up demo platform on image_process component."""
        config = {ip.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

    def test_setup_component_with_service(self):
        """Set up demo platform on image_process component test service."""
        config = {ip.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.services.has_service(ip.DOMAIN, "scan")


class TestImageProcessing:
    """Test class for image processing."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        setup_component(
            self.hass,
            http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: get_test_instance_port()}},
        )

        config = {ip.DOMAIN: {"platform": "test"}, "camera": {"platform": "demo"}}

        setup_component(self.hass, ip.DOMAIN, config)

        state = self.hass.states.get("camera.demo_camera")
        self.url = f"{self.hass.config.api.base_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.demo.camera.DemoCamera.camera_image",
        autospec=True,
        return_value=b"Test",
    )
    def test_get_image_from_camera(self, mock_camera):
        """Grab an image from camera entity."""
        common.scan(self.hass, entity_id="image_processing.test")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.test")

        assert mock_camera.called
        assert state.state == "1"
        assert state.attributes["image"] == b"Test"

    @patch(
        "homeassistant.components.camera.async_get_image",
        side_effect=HomeAssistantError(),
    )
    def test_get_image_without_exists_camera(self, mock_image):
        """Try to get image without exists camera."""
        self.hass.states.remove("camera.demo_camera")

        common.scan(self.hass, entity_id="image_processing.test")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.test")

        assert mock_image.called
        assert state.state == "0"


class TestImageProcessingAlpr:
    """Test class for alpr image processing."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        config = {ip.DOMAIN: {"platform": "demo"}, "camera": {"platform": "demo"}}

        with patch(
            "homeassistant.components.demo.image_processing."
            "DemoImageProcessingAlpr.should_poll",
            new_callable=PropertyMock(return_value=False),
        ):
            setup_component(self.hass, ip.DOMAIN, config)

        state = self.hass.states.get("camera.demo_camera")
        self.url = f"{self.hass.config.api.base_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"

        self.alpr_events = []

        @callback
        def mock_alpr_event(event):
            """Mock event."""
            self.alpr_events.append(event)

        self.hass.bus.listen("image_processing.found_plate", mock_alpr_event)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_alpr_event_single_call(self, aioclient_mock):
        """Set up and scan a picture and test plates from event."""
        aioclient_mock.get(self.url, content=b"image")

        common.scan(self.hass, entity_id="image_processing.demo_alpr")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.demo_alpr")

        assert len(self.alpr_events) == 4
        assert state.state == "AC3829"

        event_data = [
            event.data
            for event in self.alpr_events
            if event.data.get("plate") == "AC3829"
        ]
        assert len(event_data) == 1
        assert event_data[0]["plate"] == "AC3829"
        assert event_data[0]["confidence"] == 98.3
        assert event_data[0]["entity_id"] == "image_processing.demo_alpr"

    def test_alpr_event_double_call(self, aioclient_mock):
        """Set up and scan a picture and test plates from event."""
        aioclient_mock.get(self.url, content=b"image")

        common.scan(self.hass, entity_id="image_processing.demo_alpr")
        common.scan(self.hass, entity_id="image_processing.demo_alpr")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.demo_alpr")

        assert len(self.alpr_events) == 4
        assert state.state == "AC3829"

        event_data = [
            event.data
            for event in self.alpr_events
            if event.data.get("plate") == "AC3829"
        ]
        assert len(event_data) == 1
        assert event_data[0]["plate"] == "AC3829"
        assert event_data[0]["confidence"] == 98.3
        assert event_data[0]["entity_id"] == "image_processing.demo_alpr"

    @patch(
        "homeassistant.components.demo.image_processing."
        "DemoImageProcessingAlpr.confidence",
        new_callable=PropertyMock(return_value=95),
    )
    def test_alpr_event_single_call_confidence(self, confidence_mock, aioclient_mock):
        """Set up and scan a picture and test plates from event."""
        aioclient_mock.get(self.url, content=b"image")

        common.scan(self.hass, entity_id="image_processing.demo_alpr")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.demo_alpr")

        assert len(self.alpr_events) == 2
        assert state.state == "AC3829"

        event_data = [
            event.data
            for event in self.alpr_events
            if event.data.get("plate") == "AC3829"
        ]
        assert len(event_data) == 1
        assert event_data[0]["plate"] == "AC3829"
        assert event_data[0]["confidence"] == 98.3
        assert event_data[0]["entity_id"] == "image_processing.demo_alpr"


class TestImageProcessingFace:
    """Test class for face image processing."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        config = {ip.DOMAIN: {"platform": "demo"}, "camera": {"platform": "demo"}}

        with patch(
            "homeassistant.components.demo.image_processing."
            "DemoImageProcessingFace.should_poll",
            new_callable=PropertyMock(return_value=False),
        ):
            setup_component(self.hass, ip.DOMAIN, config)

        state = self.hass.states.get("camera.demo_camera")
        self.url = f"{self.hass.config.api.base_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"

        self.face_events = []

        @callback
        def mock_face_event(event):
            """Mock event."""
            self.face_events.append(event)

        self.hass.bus.listen("image_processing.detect_face", mock_face_event)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_face_event_call(self, aioclient_mock):
        """Set up and scan a picture and test faces from event."""
        aioclient_mock.get(self.url, content=b"image")

        common.scan(self.hass, entity_id="image_processing.demo_face")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.demo_face")

        assert len(self.face_events) == 2
        assert state.state == "Hans"
        assert state.attributes["total_faces"] == 4

        event_data = [
            event.data for event in self.face_events if event.data.get("name") == "Hans"
        ]
        assert len(event_data) == 1
        assert event_data[0]["name"] == "Hans"
        assert event_data[0]["confidence"] == 98.34
        assert event_data[0]["gender"] == "male"
        assert event_data[0]["entity_id"] == "image_processing.demo_face"

    @patch(
        "homeassistant.components.demo.image_processing."
        "DemoImageProcessingFace.confidence",
        new_callable=PropertyMock(return_value=None),
    )
    def test_face_event_call_no_confidence(self, mock_config, aioclient_mock):
        """Set up and scan a picture and test faces from event."""
        aioclient_mock.get(self.url, content=b"image")

        common.scan(self.hass, entity_id="image_processing.demo_face")
        self.hass.block_till_done()

        state = self.hass.states.get("image_processing.demo_face")

        assert len(self.face_events) == 3
        assert state.state == "4"
        assert state.attributes["total_faces"] == 4

        event_data = [
            event.data for event in self.face_events if event.data.get("name") == "Hans"
        ]
        assert len(event_data) == 1
        assert event_data[0]["name"] == "Hans"
        assert event_data[0]["confidence"] == 98.34
        assert event_data[0]["gender"] == "male"
        assert event_data[0]["entity_id"] == "image_processing.demo_face"
