"""The tests for the pushbullet notification platform."""
import json
import unittest

from pushbullet import PushBullet
import requests_mock

import homeassistant.components.notify as notify
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant, load_fixture


class TestPushBullet(unittest.TestCase):
    """Tests the Pushbullet Component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that we started."""
        self.hass.stop()

    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_config(self, mock__get_data):
        """Test setup."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    def test_pushbullet_config_bad(self):
        """Test set up the platform with bad/missing configuration."""
        config = {notify.DOMAIN: {"platform": "pushbullet"}}
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_default(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {"title": "Test Title", "message": "Test Message"}
        self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
        assert mock.called
        assert mock.call_count == 1

        expected_body = {"body": "Test Message", "title": "Test Title", "type": "note"}
        assert mock.last_request.json() == expected_body

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_device(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {
            "title": "Test Title",
            "message": "Test Message",
            "target": ["device/DESKTOP"],
        }
        self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "body": "Test Message",
            "device_iden": "identity1",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.last_request.json() == expected_body

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_devices(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {
            "title": "Test Title",
            "message": "Test Message",
            "target": ["device/DESKTOP", "device/My iPhone"],
        }
        self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
        assert mock.called
        assert mock.call_count == 2
        assert len(mock.request_history) == 2

        expected_body = {
            "body": "Test Message",
            "device_iden": "identity1",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.request_history[0].json() == expected_body
        expected_body = {
            "body": "Test Message",
            "device_iden": "identity2",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.request_history[1].json() == expected_body

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_email(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {
            "title": "Test Title",
            "message": "Test Message",
            "target": ["email/user@host.net"],
        }
        self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
        assert mock.called
        assert mock.call_count == 1
        assert len(mock.request_history) == 1

        expected_body = {
            "body": "Test Message",
            "email": "user@host.net",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.request_history[0].json() == expected_body

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_mixed(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {
            "title": "Test Title",
            "message": "Test Message",
            "target": ["device/DESKTOP", "email/user@host.net"],
        }
        self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
        assert mock.called
        assert mock.call_count == 2
        assert len(mock.request_history) == 2

        expected_body = {
            "body": "Test Message",
            "device_iden": "identity1",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.request_history[0].json() == expected_body
        expected_body = {
            "body": "Test Message",
            "email": "user@host.net",
            "title": "Test Title",
            "type": "note",
        }
        assert mock.request_history[1].json() == expected_body

    @requests_mock.Mocker()
    @patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("pushbullet_devices.json")),
    )
    def test_pushbullet_push_no_file(self, mock, mock__get_data):
        """Test pushbullet push to default target."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "pushbullet",
                "api_key": "MYFAKEKEY",
            }
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        mock.register_uri(
            requests_mock.POST,
            "https://api.pushbullet.com/v2/pushes",
            status_code=200,
            json={"mock_response": "Ok"},
        )
        data = {
            "title": "Test Title",
            "message": "Test Message",
            "target": ["device/DESKTOP", "device/My iPhone"],
            "data": {"file": "not_a_file"},
        }
        assert not self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
