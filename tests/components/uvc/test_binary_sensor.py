"""The tests for UVC camera module."""
import asyncio
import logging
import unittest
from unittest import mock

from homeassistant.components.binary_sensor import DEVICE_CLASS_CONNECTIVITY
from homeassistant.components.uvc import binary_sensor as sensor
from homeassistant.components.uvc.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestUVCBinarySensorSetup(unittest.TestCase):
    """Test the UVC camera platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)
        self.coordinator = DataUpdateCoordinator(
            self.hass, _LOGGER, name="unifi-video-test"
        )

    def test_setup_config(self):
        """Test component setup."""
        self.hass.data[DOMAIN] = {}
        self.hass.data[DOMAIN]["coordinator"] = self.coordinator
        self.hass.data[DOMAIN]["camera_id_field"] = "id"

        self.coordinator.data = {
            "uuid-1": {"id": "uuid-1", "name": "camera-1"},
            "uuid-2": {"id": "uuid-2", "name": "camera-2"},
        }

        add_entities = mock.MagicMock()
        assert asyncio.run_coroutine_threadsafe(
            sensor.async_setup_entry(self.hass, {}, add_entities), self.hass.loop
        ).result()
        self.hass.block_till_done()

        assert add_entities.call_count == 1


class TestUnifiVideoCameraConnectionSensor(unittest.TestCase):
    """Test class for UVC."""

    def setup_method(self, method):
        """Set up the mock camera."""
        self.uuid = "06e3ff29-8048-31c2-8574-0852d1bd0e03"
        self.name = "name"
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)
        self.coordinator = DataUpdateCoordinator(
            self.hass, _LOGGER, name="unifi-video-test"
        )
        self.coordinator.data = {
            "06e3ff29-8048-31c2-8574-0852d1bd0e03": {
                "model": "UVC Fake",
                "uuid": "06e3ff29-8048-31c2-8574-0852d1bd0e03",
                "recordingSettings": {"fullTimeRecordEnabled": True},
                "host": "host-a",
                "state": "DISCONNECTED",
                "internalHost": "host-b",
                "username": "admin",
                "channels": [
                    {
                        "id": "0",
                        "width": 1920,
                        "height": 1080,
                        "fps": 25,
                        "bitrate": 6000000,
                        "isRtspEnabled": True,
                        "rtspUris": [
                            "rtsp://host-a:7447/uuid_rtspchannel_0",
                            "rtsp://foo:7447/uuid_rtspchannel_0",
                        ],
                    },
                    {
                        "id": "1",
                        "width": 1024,
                        "height": 576,
                        "fps": 15,
                        "bitrate": 1200000,
                        "isRtspEnabled": False,
                        "rtspUris": [
                            "rtsp://host-a:7447/uuid_rtspchannel_1",
                            "rtsp://foo:7447/uuid_rtspchannel_1",
                        ],
                    },
                ],
            }
        }
        self.uvc = sensor.UnifiVideoCameraConnectionSensor(
            self.coordinator, self.uuid, self.name
        )

    def test_properties(self):
        """Test the properties."""
        assert "name Connection Status" == self.uvc.name
        assert DEVICE_CLASS_CONNECTIVITY == self.uvc.device_class
        assert (
            "06e3ff29-8048-31c2-8574-0852d1bd0e03-connection-status"
            == self.uvc.unique_id
        )

    def test_device_info(self):
        """Test device information."""
        assert {
            ("uvc", "06e3ff29-8048-31c2-8574-0852d1bd0e03")
        } == self.uvc.device_info["identifiers"]
        assert "Ubiquiti" == self.uvc.device_info["manufacturer"]
        assert "UVC Fake" == self.uvc.device_info["model"]

    def test_is_on(self):
        """Test the is_on property."""
        self.coordinator.data[self.uuid]["state"] = "CONNECTED"
        assert STATE_ON == self.uvc.state

        self.coordinator.data[self.uuid]["state"] = "DISCONNECTED"
        assert STATE_OFF == self.uvc.state
