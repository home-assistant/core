"""The tests for UVC camera module."""
import socket
import unittest
from unittest import mock

import requests
from uvcclient import camera
from uvcclient import nvr

from homeassistant.bootstrap import setup_component
from homeassistant.components.camera import uvc


class TestUVCSetup(unittest.TestCase):
    """Test the UVC camera platform."""

    @mock.patch('uvcclient.nvr.UVCRemote')
    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_full_config(self, mock_uvc, mock_remote):
        """"Test the setup with full configuration."""
        config = {
            'platform': 'uvc',
            'nvr': 'foo',
            'port': 123,
            'key': 'secret',
        }
        fake_cameras = [
            {'uuid': 'one', 'name': 'Front', 'id': 'id1'},
            {'uuid': 'two', 'name': 'Back', 'id': 'id2'},
            {'uuid': 'three', 'name': 'Old AirCam', 'id': 'id3'},
        ]

        def fake_get_camera(uuid):
            """"Create a fake camera."""
            if uuid == 'id3':
                return {'model': 'airCam'}
            else:
                return {'model': 'UVC'}

        hass = mock.MagicMock()
        hass.config.components = ['http']
        mock_remote.return_value.index.return_value = fake_cameras
        mock_remote.return_value.get_camera.side_effect = fake_get_camera
        mock_remote.return_value.server_version = (3, 2, 0)

        assert setup_component(hass, 'camera', {'camera': config})

        mock_remote.assert_called_once_with('foo', 123, 'secret')
        mock_uvc.assert_has_calls([
            mock.call(mock_remote.return_value, 'id1', 'Front'),
            mock.call(mock_remote.return_value, 'id2', 'Back'),
        ])

    @mock.patch('uvcclient.nvr.UVCRemote')
    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_partial_config(self, mock_uvc, mock_remote):
        """"Test the setup with partial configuration."""
        config = {
            'platform': 'uvc',
            'nvr': 'foo',
            'key': 'secret',
        }
        fake_cameras = [
            {'uuid': 'one', 'name': 'Front', 'id': 'id1'},
            {'uuid': 'two', 'name': 'Back', 'id': 'id2'},
        ]
        hass = mock.MagicMock()
        hass.config.components = ['http']
        mock_remote.return_value.index.return_value = fake_cameras
        mock_remote.return_value.get_camera.return_value = {'model': 'UVC'}
        mock_remote.return_value.server_version = (3, 2, 0)

        assert setup_component(hass, 'camera', {'camera': config})

        mock_remote.assert_called_once_with('foo', 7080, 'secret')
        mock_uvc.assert_has_calls([
            mock.call(mock_remote.return_value, 'id1', 'Front'),
            mock.call(mock_remote.return_value, 'id2', 'Back'),
        ])

    @mock.patch('uvcclient.nvr.UVCRemote')
    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_partial_config_v31x(self, mock_uvc, mock_remote):
        """Test the setup with a v3.1.x server."""
        config = {
            'platform': 'uvc',
            'nvr': 'foo',
            'key': 'secret',
        }
        fake_cameras = [
            {'uuid': 'one', 'name': 'Front', 'id': 'id1'},
            {'uuid': 'two', 'name': 'Back', 'id': 'id2'},
        ]
        hass = mock.MagicMock()
        hass.config.components = ['http']
        mock_remote.return_value.index.return_value = fake_cameras
        mock_remote.return_value.get_camera.return_value = {'model': 'UVC'}
        mock_remote.return_value.server_version = (3, 1, 3)

        assert setup_component(hass, 'camera', {'camera': config})

        mock_remote.assert_called_once_with('foo', 7080, 'secret')
        mock_uvc.assert_has_calls([
            mock.call(mock_remote.return_value, 'one', 'Front'),
            mock.call(mock_remote.return_value, 'two', 'Back'),
        ])

    @mock.patch.object(uvc, 'UnifiVideoCamera')
    def test_setup_incomplete_config(self, mock_uvc):
        """"Test the setup with incomplete configuration."""
        hass = mock.MagicMock()
        hass.config.components = ['http']

        assert setup_component(
            hass, 'camera', {'platform': 'uvc', 'nvr': 'foo'})
        assert not mock_uvc.called
        assert setup_component(
            hass, 'camera', {'platform': 'uvc', 'key': 'secret'})
        assert not mock_uvc.called
        assert setup_component(
            hass, 'camera', {'platform': 'uvc', 'port': 'invalid'})
        assert not mock_uvc.called

    @mock.patch.object(uvc, 'UnifiVideoCamera')
    @mock.patch('uvcclient.nvr.UVCRemote')
    def test_setup_nvr_errors(self, mock_remote, mock_uvc):
        """"Test for NVR errors."""
        errors = [nvr.NotAuthorized, nvr.NvrError,
                  requests.exceptions.ConnectionError]
        config = {
            'platform': 'uvc',
            'nvr': 'foo',
            'key': 'secret',
        }
        hass = mock.MagicMock()
        hass.config.components = ['http']

        for error in errors:
            mock_remote.return_value.index.side_effect = error
            assert setup_component(hass, 'camera', config)
            assert not mock_uvc.called


class TestUVC(unittest.TestCase):
    """Test class for UVC."""

    def setup_method(self, method):
        """"Setup the mock camera."""
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
        self.nvr.server_version = (3, 2, 0)

    def test_properties(self):
        """"Test the properties."""
        self.assertEqual(self.name, self.uvc.name)
        self.assertTrue(self.uvc.is_recording)
        self.assertEqual('Ubiquiti', self.uvc.brand)
        self.assertEqual('UVC Fake', self.uvc.model)

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClientV320')
    def test_login(self, mock_camera, mock_store):
        """"Test the login."""
        mock_store.return_value.get_camera_password.return_value = 'seekret'
        self.uvc._login()
        mock_camera.assert_called_once_with('host-a', 'admin', 'seekret')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClient')
    def test_login_v31x(self, mock_camera, mock_store):
        """Test login with v3.1.x server."""
        mock_store.return_value.get_camera_password.return_value = 'seekret'
        self.nvr.server_version = (3, 1, 3)
        self.uvc._login()
        mock_camera.assert_called_once_with('host-a', 'admin', 'seekret')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClientV320')
    def test_login_no_password(self, mock_camera, mock_store):
        """"Test the login with no password."""
        mock_store.return_value.get_camera_password.return_value = None
        self.uvc._login()
        mock_camera.assert_called_once_with('host-a', 'admin', 'ubnt')
        mock_camera.return_value.login.assert_called_once_with()

    @mock.patch('uvcclient.store.get_info_store')
    @mock.patch('uvcclient.camera.UVCCameraClientV320')
    def test_login_tries_both_addrs_and_caches(self, mock_camera, mock_store):
        """"Test the login tries."""
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
    @mock.patch('uvcclient.camera.UVCCameraClientV320')
    def test_login_fails_both_properly(self, mock_camera, mock_store):
        """"Test if login fails properly."""
        mock_camera.return_value.login.side_effect = socket.error
        self.assertEqual(None, self.uvc._login())
        self.assertEqual(None, self.uvc._connect_addr)

    def test_camera_image_tries_login_bails_on_failure(self):
        """"Test retrieving failure."""
        with mock.patch.object(self.uvc, '_login') as mock_login:
            mock_login.return_value = False
            self.assertEqual(None, self.uvc.camera_image())
            mock_login.assert_called_once_with()

    def test_camera_image_logged_in(self):
        """"Test the login state."""
        self.uvc._camera = mock.MagicMock()
        self.assertEqual(self.uvc._camera.get_snapshot.return_value,
                         self.uvc.camera_image())

    def test_camera_image_error(self):
        """"Test the camera image error."""
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraConnectError
        self.assertEqual(None, self.uvc.camera_image())

    def test_camera_image_reauths(self):
        """"Test the re-authentication."""
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
        """"Test if the re-authentication only happens once."""
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraAuthError
        with mock.patch.object(self.uvc, '_login') as mock_login:
            self.assertRaises(camera.CameraAuthError, self.uvc.camera_image)
            mock_login.assert_called_once_with()
