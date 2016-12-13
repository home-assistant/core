"""The tests for the APNS component."""
import unittest
import os

import homeassistant.components.notify as notify
from homeassistant.core import State
from homeassistant.components.notify.apns import ApnsNotificationService
from tests.common import get_test_home_assistant
from homeassistant.config import load_yaml_config_file
from unittest.mock import patch
from apns2.errors import Unregistered


class TestApns(unittest.TestCase):
    """Test the APNS component."""

    def test_apns_setup_full(self):
        """Test setup with all data."""
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'sandbox': 'True',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        self.assertTrue(notify.setup(hass, config))

    def test_apns_setup_missing_name(self):
        """Test setup with missing name."""
        config = {
            'notify': {
                'platform': 'apns',
                'sandbox': 'True',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()
        self.assertFalse(notify.setup(hass, config))

    def test_apns_setup_missing_certificate(self):
        """Test setup with missing name."""
        config = {
            'notify': {
                'platform': 'apns',
                'topic': 'testapp.appname',
                'name': 'test_app'
            }
        }
        hass = get_test_home_assistant()
        self.assertFalse(notify.setup(hass, config))

    def test_apns_setup_missing_topic(self):
        """Test setup with missing topic."""
        config = {
            'notify': {
                'platform': 'apns',
                'cert_file': 'test_app.pem',
                'name': 'test_app'
            }
        }
        hass = get_test_home_assistant()
        self.assertFalse(notify.setup(hass, config))

    def test_register_new_device(self):
        """Test registering a new device with a name."""
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('5678: {name: test device 2}\n')

        notify.setup(hass, config)
        self.assertTrue(hass.services.call('apns',
                                           'test_app',
                                           {'push_id': '1234',
                                            'name': 'test device'},
                                           blocking=True))

        devices = {str(key): value for (key, value) in
                   load_yaml_config_file(devices_path).items()}

        test_device_1 = devices.get('1234')
        test_device_2 = devices.get('5678')

        self.assertIsNotNone(test_device_1)
        self.assertIsNotNone(test_device_2)

        self.assertEqual('test device', test_device_1.get('name'))

        os.remove(devices_path)

    def test_register_device_without_name(self):
        """Test registering a without a name."""
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('5678: {name: test device 2}\n')

        notify.setup(hass, config)
        self.assertTrue(hass.services.call('apns', 'test_app',
                                           {'push_id': '1234'},
                                           blocking=True))

        devices = {str(key): value for (key, value) in
                   load_yaml_config_file(devices_path).items()}

        test_device = devices.get('1234')

        self.assertIsNotNone(test_device)
        self.assertIsNone(test_device.get('name'))

        os.remove(devices_path)

    def test_update_existing_device(self):
        """Test updating an existing device."""
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1}\n')
            out.write('5678: {name: test device 2}\n')

        notify.setup(hass, config)
        self.assertTrue(hass.services.call('apns',
                                           'test_app',
                                           {'push_id': '1234',
                                            'name': 'updated device 1'},
                                           blocking=True))

        devices = {str(key): value for (key, value) in
                   load_yaml_config_file(devices_path).items()}

        test_device_1 = devices.get('1234')
        test_device_2 = devices.get('5678')

        self.assertIsNotNone(test_device_1)
        self.assertIsNotNone(test_device_2)

        self.assertEqual('updated device 1', test_device_1.get('name'))

        os.remove(devices_path)

    def test_update_existing_device_with_tracking_id(self):
        """Test updating an existing device that has a tracking id."""
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1, '
                      'tracking_device_id: tracking123}\n')
            out.write('5678: {name: test device 2, '
                      'tracking_device_id: tracking456}\n')

        notify.setup(hass, config)
        self.assertTrue(hass.services.call('apns',
                                           'test_app',
                                           {'push_id': '1234',
                                            'name': 'updated device 1'},
                                           blocking=True))

        devices = {str(key): value for (key, value) in
                   load_yaml_config_file(devices_path).items()}

        test_device_1 = devices.get('1234')
        test_device_2 = devices.get('5678')

        self.assertIsNotNone(test_device_1)
        self.assertIsNotNone(test_device_2)

        self.assertEqual('tracking123',
                         test_device_1.get('tracking_device_id'))
        self.assertEqual('tracking456',
                         test_device_2.get('tracking_device_id'))

        os.remove(devices_path)

    @patch('apns2.client.APNsClient')
    def test_send(self, mock_client):
        """Test updating an existing device."""
        send = mock_client.return_value.send_notification
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1}\n')

        notify.setup(hass, config)

        self.assertTrue(hass.services.call('notify', 'test_app',
                                           {'message': 'Hello',
                                            'data': {
                                                'badge': 1,
                                                'sound': 'test.mp3',
                                                'category': 'testing'
                                                }
                                            },
                                           blocking=True))

        self.assertTrue(send.called)
        self.assertEqual(1, len(send.mock_calls))

        target = send.mock_calls[0][1][0]
        payload = send.mock_calls[0][1][1]

        self.assertEqual('1234', target)
        self.assertEqual('Hello', payload.alert)
        self.assertEqual(1, payload.badge)
        self.assertEqual('test.mp3', payload.sound)
        self.assertEqual('testing', payload.category)

    @patch('apns2.client.APNsClient')
    def test_send_when_disabled(self, mock_client):
        """Test updating an existing device."""
        send = mock_client.return_value.send_notification
        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1, disabled: True}\n')

        notify.setup(hass, config)

        self.assertTrue(hass.services.call('notify', 'test_app',
                                           {'message': 'Hello',
                                            'data': {
                                                'badge': 1,
                                                'sound': 'test.mp3',
                                                'category': 'testing'
                                            }
                                            },
                                           blocking=True))

        self.assertFalse(send.called)

    @patch('apns2.client.APNsClient')
    def test_send_with_state(self, mock_client):
        """Test updating an existing device."""
        send = mock_client.return_value.send_notification

        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1, '
                      'tracking_device_id: tracking123}\n')
            out.write('5678: {name: test device 2, '
                      'tracking_device_id: tracking456}\n')

        notify_service = ApnsNotificationService(
            hass,
            'test_app',
            'testapp.appname',
            False,
            'test_app.pem'
        )

        notify_service.device_state_changed_listener(
            'device_tracker.tracking456',
            State('device_tracker.tracking456', None),
            State('device_tracker.tracking456', 'home'))

        hass.block_till_done()

        notify_service.send_message(message='Hello', target='home')

        self.assertTrue(send.called)
        self.assertEqual(1, len(send.mock_calls))

        target = send.mock_calls[0][1][0]
        payload = send.mock_calls[0][1][1]

        self.assertEqual('5678', target)
        self.assertEqual('Hello', payload.alert)

    @patch('apns2.client.APNsClient')
    def test_disable_when_unregistered(self, mock_client):
        """Test disabling a device when it is unregistered."""
        send = mock_client.return_value.send_notification
        send.side_effect = Unregistered()

        config = {
            'notify': {
                'platform': 'apns',
                'name': 'test_app',
                'topic': 'testapp.appname',
                'cert_file': 'test_app.pem'
            }
        }
        hass = get_test_home_assistant()

        devices_path = hass.config.path('test_app_apns.yaml')
        with open(devices_path, 'w+') as out:
            out.write('1234: {name: test device 1}\n')

        notify.setup(hass, config)

        self.assertTrue(hass.services.call('notify', 'test_app',
                                           {'message': 'Hello'},
                                           blocking=True))

        devices = {str(key): value for (key, value) in
                   load_yaml_config_file(devices_path).items()}

        test_device_1 = devices.get('1234')
        self.assertIsNotNone(test_device_1)
        self.assertEqual(True, test_device_1.get('disabled'))

        os.remove(devices_path)
