"""The tests for the Ring binary sensor platform."""
import time
import unittest
from unittest import mock

from homeassistant.components.binary_sensor import ring
from tests.common import get_test_home_assistant

VALID_CONFIG = {
    "platform": "ring",
    "username": "foo",
    "password": "bar",
    "monitored_conditions": [
        "ding", "motion"
    ]
}

ATTRIBUTION = 'Data provided by Ring.com'


def mocked_requests_get(*args, **kwargs):
    """Mock requests.get invocations."""
    class MockResponse:
        """Class to represent a mocked response."""

        def __init__(self, json_data, status_code):
            """Initialize the mock response class."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Return the json of the response."""
            return self.json_data

    if str(args[0]).startswith('https://api.ring.com/clients_api/session'):
        return MockResponse({
            "profile": {
                "authentication_token": "12345678910",
                "email": "foo@bar.org",
                "features": {
                    "chime_dnd_enabled": False,
                    "chime_pro_enabled": True,
                    "delete_all_enabled": True,
                    "delete_all_settings_enabled": False,
                    "device_health_alerts_enabled": True,
                    "floodlight_cam_enabled": True,
                    "live_view_settings_enabled": True,
                    "lpd_enabled": True,
                    "lpd_motion_announcement_enabled": False,
                    "multiple_calls_enabled": True,
                    "multiple_delete_enabled": True,
                    "nw_enabled": True,
                    "nw_larger_area_enabled": False,
                    "nw_user_activated": False,
                    "owner_proactive_snoozing_enabled": True,
                    "power_cable_enabled": False,
                    "proactive_snoozing_enabled": False,
                    "reactive_snoozing_enabled": False,
                    "remote_logging_format_storing": False,
                    "remote_logging_level": 1,
                    "ringplus_enabled": True,
                    "starred_events_enabled": True,
                    "stickupcam_setup_enabled": True,
                    "subscriptions_enabled": True,
                    "ujet_enabled": False,
                    "video_search_enabled": False,
                    "vod_enabled": False},
                "first_name": "Home",
                "id": 999999,
                "last_name": "Assistant"}
        }, 201)
    elif str(args[0])\
            .startswith("https://api.ring.com/clients_api/ring_devices"):
        return MockResponse({
            "authorized_doorbots": [],
            "chimes": [
                {
                    "address": "123 Main St",
                    "alerts": {"connection": "online"},
                    "description": "Downstairs",
                    "device_id": "abcdef123",
                    "do_not_disturb": {"seconds_left": 0},
                    "features": {"ringtones_enabled": True},
                    "firmware_version": "1.2.3",
                    "id": 999999,
                    "kind": "chime",
                    "latitude": 12.000000,
                    "longitude": -70.12345,
                    "owned": True,
                    "owner": {
                        "email": "foo@bar.org",
                        "first_name": "Marcelo",
                        "id": 999999,
                        "last_name": "Assistant"},
                    "settings": {
                        "ding_audio_id": None,
                        "ding_audio_user_id": None,
                        "motion_audio_id": None,
                        "motion_audio_user_id": None,
                        "volume": 2},
                    "time_zone": "America/New_York"}],
            "doorbots": [
                {
                    "address": "123 Main St",
                    "alerts": {"connection": "online"},
                    "battery_life": 4081,
                    "description": "Front Door",
                    "device_id": "aacdef123",
                    "external_connection": False,
                    "features": {
                        "advanced_motion_enabled": False,
                        "motion_message_enabled": False,
                        "motions_enabled": True,
                        "people_only_enabled": False,
                        "shadow_correction_enabled": False,
                        "show_recordings": True},
                    "firmware_version": "1.4.26",
                    "id": 987652,
                    "kind": "lpd_v1",
                    "latitude": 12.000000,
                    "longitude": -70.12345,
                    "motion_snooze": None,
                    "owned": True,
                    "owner": {
                        "email": "foo@bar.org",
                        "first_name": "Home",
                        "id": 999999,
                        "last_name": "Assistant"},
                    "settings": {
                        "chime_settings": {
                            "duration": 3,
                            "enable": True,
                            "type": 0},
                        "doorbell_volume": 1,
                        "enable_vod": True,
                        "live_view_preset_profile": "highest",
                        "live_view_presets": [
                            "low",
                            "middle",
                            "high",
                            "highest"],
                        "motion_announcement": False,
                        "motion_snooze_preset_profile": "low",
                        "motion_snooze_presets": [
                            "none",
                            "low",
                            "medium",
                            "high"]},
                    "subscribed": True,
                    "subscribed_motions": True,
                    "time_zone": "America/New_York"}]
        }, 200)
    elif str(args[0])\
            .startswith("https://api.ring.com/clients_api/dings/active"):
        return MockResponse([{
            "audio_jitter_buffer_ms": 0,
            "device_kind": "lpd_v1",
            "doorbot_description": "Front Door",
            "doorbot_id": 987652,
            "expires_in": 180,
            "id": 12345678999,
            "id_str": "12345678999",
            "kind": "ding",
            "motion": False,
            "now": time.time(),
            "optimization_level": 1,
            "protocol": "sip",
            "sip_ding_id": "12345",
            "sip_endpoints": None,
            "sip_from": "sip:99887766@ring.com",
            "sip_server_ip": "192.168.0.1",
            "sip_server_port": "15063",
            "sip_server_tls": "false",
            "sip_session_id": "secret_session",
            "sip_to": "sip:secret_session@192.168.0.1:15063;transport=tcp",
            "sip_token": "91c0bea515c0b1fce2058713b938b7d4a4a4d16aa898c",
            "snapshot_url": "",
            "state": "ringing",
            "video_jitter_buffer_ms": 0
        }], 200)


class TestRingSetup(unittest.TestCase):
    """Test the Ring platform."""

    # pylint: disable=invalid-name
    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('requests.Session.get', side_effect=mocked_requests_get)
    @mock.patch('requests.Session.post', side_effect=mocked_requests_get)
    def test_setup(self, get_mock, post_mock):
        """Test if component loaded successfully."""
        self.assertTrue(
            ring.setup_platform(self.hass, VALID_CONFIG,
                                self.add_devices, None))

    @mock.patch('requests.Session.get', side_effect=mocked_requests_get)
    @mock.patch('requests.Session.post', side_effect=mocked_requests_get)
    def test_sensor(self, get_mock, post_mock):
        """Test the Ring sensor class and methods."""
        ring.setup_platform(self.hass, VALID_CONFIG, self.add_devices, None)

        for device in self.DEVICES:
            device.update()
            if device.name == 'Front Door Ding':
                self.assertEqual('on', device.state)
                self.assertEqual('America/New_York',
                                 device.device_state_attributes['timezone'])
            elif device.name == 'Front Door Motion':
                self.assertEqual('off', device.state)
                self.assertEqual('motion', device.device_class)

            self.assertIsNone(device.entity_picture)
            self.assertEqual(ATTRIBUTION,
                             device.device_state_attributes['attribution'])
