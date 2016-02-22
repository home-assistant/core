"""
tests.components.camera.test_uvc
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for uvc camera module.
"""

import socket
import unittest
from unittest import mock

import requests
from uvcclient import camera
from uvcclient import nvr

from homeassistant.components.camera import uvc


class TestUVCSetup(unittest.TestCase):
    @mock.patch('uvcclient.nvr.UVCRemote')
    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_full_config(self, mock_uvc, mock_remote):
        config = {
            'nvr': 'foo',
            'port': 123,
            'key': 'secret',
        }
        fake_cameras = [
            {'uuid': 'one', 'name': 'Front'},
            {'uuid': 'two', 'name': 'Back'},
        ]
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()
        mock_remote.return_value.index.return_value = fake_cameras
        self.assertTrue(uvc.setup_platform(hass, config, add_devices))
        mock_remote.assert_called_once_with('foo', 123, 'secret')
        add_devices.assert_called_once_with([
            mock_uvc.return_value, mock_uvc.return_value])
        mock_uvc.assert_has_calls([
            mock.call(mock_remote.return_value, 'one', 'Front'),
            mock.call(mock_remote.return_value, 'two', 'Back'),
        ])

    @mock.patch('uvcclient.nvr.UVCRemote')
    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_partial_config(self, mock_uvc, mock_remote):
        config = {
            'nvr': 'foo',
            'key': 'secret',
        }
        fake_cameras = [
            {'uuid': 'one', 'name': 'Front'},
            {'uuid': 'two', 'name': 'Back'},
        ]
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()
        mock_remote.return_value.index.return_value = fake_cameras
        self.assertTrue(uvc.setup_platform(hass, config, add_devices))
        mock_remote.assert_called_once_with('foo', 7080, 'secret')
        add_devices.assert_called_once_with([
            mock_uvc.return_value, mock_uvc.return_value])
        mock_uvc.assert_has_calls([
            mock.call(mock_remote.return_value, 'one', 'Front'),
            mock.call(mock_remote.return_value, 'two', 'Back'),
        ])

    def test_setup_incomplete_config(self):
        self.assertFalse(uvc.setup_platform(
            None, {'nvr': 'foo'}, None))
        self.assertFalse(uvc.setup_platform(
            None, {'key': 'secret'}, None))
        self.assertFalse(uvc.setup_platform(
            None, {'port': 'invalid'}, None))

    @mock.patch('uvcclient.nvr.UVCRemote')
    def test_setup_nvr_errors(self, mock_remote):
        errors = [nvr.NotAuthorized, nvr.NvrError,
                  requests.exceptions.ConnectionError]
        config = {
            'nvr': 'foo',
            'key': 'secret',
        }
        for error in errors:
            mock_remote.return_value.index.side_effect = error
            self.assertFalse(uvc.setup_platform(None, config, None))


class TestUVC(unittest.TestCase):
    def setup_method(self, method):
        self.nvr = mock.MagicMock()
        self.uuid = 'uuid'
        self.name = 'name'
        self.uvc = uvc.UnifiVideoCamera(self.nvr, self.uuid, self.name)
        self.nvr.get_camera.return_value = {
            'model': 'UVC Fake',
            'recordingSettings': {
                'fullTimeRecordEnabled': True,
            },
            'host': 'host-a',
            'internalHost': 'host-b',
            'username': 'admin',
        }

    def test_properties(self):
        self.assertEqual(self.name, self.uvc.name)
        self.assertTrue(self.uvc.is_recording)
        self.assertEqual('Ubiquiti', self.uvc.brand)
        self.assertEqual('UVC Fake', self.uvc.model)

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClient')
    def test_login(self, mock_camera, mock_store):
        mock_store.return_value.get_camera_password.return_value = 'seekret'
        self.uvc._login()
        mock_camera.assert_called_once_with('host-a', 'admin', 'seekret')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClient')
    def test_login_no_password(self, mock_camera, mock_store):
        mock_store.return_value.get_camera_password.return_value = None
        self.uvc._login()
        mock_camera.assert_called_once_with('host-a', 'admin', 'ubnt')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClient')
    def test_login_tries_both_addrs_and_caches(self, mock_camera, mock_store):
        responses = [0]

        def fake_login(*a):
            try:
                responses.pop(0)
                raise socket.error
            except IndexError:
                pass

        mock_store.return_value.get_camera_password.return_value = None
        mock_camera.return_value.login.side_effect = fake_login
        self.uvc._login()
        self.assertEqual(2, mock_camera.call_count)
        self.assertEqual('host-b', self.uvc._connect_addr)

        mock_camera.reset_mock()
        self.uvc._login()
        mock_camera.assert_called_once_with('host-b', 'admin', 'ubnt')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClient')
    def test_login_fails_both_properly(self, mock_camera, mock_store):
        mock_camera.return_value.login.side_effect = socket.error
        self.assertEqual(None, self.uvc._login())
        self.assertEqual(None, self.uvc._connect_addr)

    def test_camera_image_tries_login_bails_on_failure(self):
        with mock.patch.object(self.uvc, '_login') as mock_login:
            mock_login.return_value = False
            self.assertEqual(None, self.uvc.camera_image())
            mock_login.assert_called_once_with()

    def test_camera_image_logged_in(self):
        self.uvc._camera = mock.MagicMock()
        self.assertEqual(self.uvc._camera.get_snapshot.return_value,
                         self.uvc.camera_image())

    def test_camera_image_error(self):
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraConnectError
        self.assertEqual(None, self.uvc.camera_image())

    def test_camera_image_reauths(self):
        responses = [0]

        def fake_snapshot():
            try:
                responses.pop()
                raise camera.CameraAuthError()
            except IndexError:
                pass
            return 'image'

        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = fake_snapshot
        with mock.patch.object(self.uvc, '_login') as mock_login:
            self.assertEqual('image', self.uvc.camera_image())
            mock_login.assert_called_once_with()
            self.assertEqual([], responses)

    def test_camera_image_reauths_only_once(self):
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraAuthError
        with mock.patch.object(self.uvc, '_login') as mock_login:
            self.assertRaises(camera.CameraAuthError, self.uvc.camera_image)
            mock_login.assert_called_once_with()
