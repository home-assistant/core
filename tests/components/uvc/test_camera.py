"""The tests for UVC camera module."""
import socket
import unittest
from unittest import mock

import pytest
import requests
from uvcclient import camera, nvr

from homeassistant.components.camera import SUPPORT_STREAM
from homeassistant.components.uvc import camera as uvc
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestUVCSetup(unittest.TestCase):
    """Test the UVC camera platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    @mock.patch("uvcclient.nvr.UVCRemote")
    @mock.patch.object(uvc, "UnifiVideoCamera")
    def test_setup_full_config(self, mock_uvc, mock_remote):
        """Test the setup with full configuration."""
        config = {
            "platform": "uvc",
            "nvr": "foo",
            "password": "bar",
            "port": 123,
            "key": "secret",
        }
        mock_cameras = [
            {"uuid": "one", "name": "Front", "id": "id1"},
            {"uuid": "two", "name": "Back", "id": "id2"},
            {"uuid": "three", "name": "Old AirCam", "id": "id3"},
        ]

        def mock_get_camera(uuid):
            """Create a mock camera."""
            if uuid == "id3":
                return {"model": "airCam"}
            return {"model": "UVC"}

        mock_remote.return_value.index.return_value = mock_cameras
        mock_remote.return_value.get_camera.side_effect = mock_get_camera
        mock_remote.return_value.server_version = (3, 2, 0)

        assert setup_component(self.hass, "camera", {"camera": config})
        self.hass.block_till_done()

        assert mock_remote.call_count == 1
        assert mock_remote.call_args == mock.call("foo", 123, "secret", ssl=False)
        mock_uvc.assert_has_calls(
            [
                mock.call(mock_remote.return_value, "id1", "Front", "bar"),
                mock.call(mock_remote.return_value, "id2", "Back", "bar"),
            ]
        )

    @mock.patch("uvcclient.nvr.UVCRemote")
    @mock.patch.object(uvc, "UnifiVideoCamera")
    def test_setup_partial_config(self, mock_uvc, mock_remote):
        """Test the setup with partial configuration."""
        config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
        mock_cameras = [
            {"uuid": "one", "name": "Front", "id": "id1"},
            {"uuid": "two", "name": "Back", "id": "id2"},
        ]
        mock_remote.return_value.index.return_value = mock_cameras
        mock_remote.return_value.get_camera.return_value = {"model": "UVC"}
        mock_remote.return_value.server_version = (3, 2, 0)

        assert setup_component(self.hass, "camera", {"camera": config})
        self.hass.block_till_done()

        assert mock_remote.call_count == 1
        assert mock_remote.call_args == mock.call("foo", 7080, "secret", ssl=False)
        mock_uvc.assert_has_calls(
            [
                mock.call(mock_remote.return_value, "id1", "Front", "ubnt"),
                mock.call(mock_remote.return_value, "id2", "Back", "ubnt"),
            ]
        )

    @mock.patch("uvcclient.nvr.UVCRemote")
    @mock.patch.object(uvc, "UnifiVideoCamera")
    def test_setup_partial_config_v31x(self, mock_uvc, mock_remote):
        """Test the setup with a v3.1.x server."""
        config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
        mock_cameras = [
            {"uuid": "one", "name": "Front", "id": "id1"},
            {"uuid": "two", "name": "Back", "id": "id2"},
        ]
        mock_remote.return_value.index.return_value = mock_cameras
        mock_remote.return_value.get_camera.return_value = {"model": "UVC"}
        mock_remote.return_value.server_version = (3, 1, 3)

        assert setup_component(self.hass, "camera", {"camera": config})
        self.hass.block_till_done()

        assert mock_remote.call_count == 1
        assert mock_remote.call_args == mock.call("foo", 7080, "secret", ssl=False)
        mock_uvc.assert_has_calls(
            [
                mock.call(mock_remote.return_value, "one", "Front", "ubnt"),
                mock.call(mock_remote.return_value, "two", "Back", "ubnt"),
            ]
        )

    @mock.patch.object(uvc, "UnifiVideoCamera")
    def test_setup_incomplete_config(self, mock_uvc):
        """Test the setup with incomplete configuration."""
        assert setup_component(self.hass, "camera", {"platform": "uvc", "nvr": "foo"})
        self.hass.block_till_done()

        assert not mock_uvc.called
        assert setup_component(
            self.hass, "camera", {"platform": "uvc", "key": "secret"}
        )
        self.hass.block_till_done()

        assert not mock_uvc.called
        assert setup_component(
            self.hass, "camera", {"platform": "uvc", "port": "invalid"}
        )
        self.hass.block_till_done()

        assert not mock_uvc.called

    @mock.patch.object(uvc, "UnifiVideoCamera")
    @mock.patch("uvcclient.nvr.UVCRemote")
    def setup_nvr_errors_during_indexing(self, error, mock_remote, mock_uvc):
        """Set up test for NVR errors during indexing."""
        config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
        mock_remote.return_value.index.side_effect = error
        assert setup_component(self.hass, "camera", {"camera": config})
        self.hass.block_till_done()

        assert not mock_uvc.called

    def test_setup_nvr_error_during_indexing_notauthorized(self):
        """Test for error: nvr.NotAuthorized."""
        self.setup_nvr_errors_during_indexing(nvr.NotAuthorized)

    def test_setup_nvr_error_during_indexing_nvrerror(self):
        """Test for error: nvr.NvrError."""
        self.setup_nvr_errors_during_indexing(nvr.NvrError)
        pytest.raises(PlatformNotReady)

    def test_setup_nvr_error_during_indexing_connectionerror(self):
        """Test for error: requests.exceptions.ConnectionError."""
        self.setup_nvr_errors_during_indexing(requests.exceptions.ConnectionError)
        pytest.raises(PlatformNotReady)

    @mock.patch.object(uvc, "UnifiVideoCamera")
    @mock.patch("uvcclient.nvr.UVCRemote.__init__")
    def setup_nvr_errors_during_initialization(self, error, mock_remote, mock_uvc):
        """Set up test for NVR errors during initialization."""
        config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
        mock_remote.return_value = None
        mock_remote.side_effect = error
        assert setup_component(self.hass, "camera", {"camera": config})
        self.hass.block_till_done()

        assert not mock_remote.index.called
        assert not mock_uvc.called

    def test_setup_nvr_error_during_initialization_notauthorized(self):
        """Test for error: nvr.NotAuthorized."""
        self.setup_nvr_errors_during_initialization(nvr.NotAuthorized)

    def test_setup_nvr_error_during_initialization_nvrerror(self):
        """Test for error: nvr.NvrError."""
        self.setup_nvr_errors_during_initialization(nvr.NvrError)
        pytest.raises(PlatformNotReady)

    def test_setup_nvr_error_during_initialization_connectionerror(self):
        """Test for error: requests.exceptions.ConnectionError."""
        self.setup_nvr_errors_during_initialization(requests.exceptions.ConnectionError)
        pytest.raises(PlatformNotReady)


class TestUVC(unittest.TestCase):
    """Test class for UVC."""

    def setup_method(self, method):
        """Set up the mock camera."""
        self.nvr = mock.MagicMock()
        self.uuid = "uuid"
        self.name = "name"
        self.password = "seekret"
        self.uvc = uvc.UnifiVideoCamera(self.nvr, self.uuid, self.name, self.password)
        self.nvr.get_camera.return_value = {
            "model": "UVC Fake",
            "uuid": "06e3ff29-8048-31c2-8574-0852d1bd0e03",
            "recordingSettings": {"fullTimeRecordEnabled": True},
            "host": "host-a",
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
        self.nvr.server_version = (3, 2, 0)
        self.uvc.update()

    def test_properties(self):
        """Test the properties."""
        assert self.name == self.uvc.name
        assert self.uvc.is_recording
        assert "Ubiquiti" == self.uvc.brand
        assert "UVC Fake" == self.uvc.model
        assert SUPPORT_STREAM == self.uvc.supported_features
        assert "uuid" == self.uvc.unique_id

    def test_stream(self):
        """Test the RTSP stream URI."""
        stream_source = yield from self.uvc.stream_source()
        assert stream_source == "rtsp://foo:7447/uuid_rtspchannel_0"

    @mock.patch("uvcclient.store.get_info_store")
    @mock.patch("uvcclient.camera.UVCCameraClientV320")
    def test_login(self, mock_camera, mock_store):
        """Test the login."""
        self.uvc._login()
        assert mock_camera.call_count == 1
        assert mock_camera.call_args == mock.call("host-a", "admin", "seekret")
        assert mock_camera.return_value.login.call_count == 1
        assert mock_camera.return_value.login.call_args == mock.call()

    @mock.patch("uvcclient.store.get_info_store")
    @mock.patch("uvcclient.camera.UVCCameraClient")
    def test_login_v31x(self, mock_camera, mock_store):
        """Test login with v3.1.x server."""
        self.nvr.server_version = (3, 1, 3)
        self.uvc._login()
        assert mock_camera.call_count == 1
        assert mock_camera.call_args == mock.call("host-a", "admin", "seekret")
        assert mock_camera.return_value.login.call_count == 1
        assert mock_camera.return_value.login.call_args == mock.call()

    @mock.patch("uvcclient.store.get_info_store")
    @mock.patch("uvcclient.camera.UVCCameraClientV320")
    def test_login_tries_both_addrs_and_caches(self, mock_camera, mock_store):
        """Test the login tries."""
        responses = [0]

        def mock_login(*a):
            """Mock login."""
            try:
                responses.pop(0)
                raise OSError
            except IndexError:
                pass

        mock_store.return_value.get_camera_password.return_value = None
        mock_camera.return_value.login.side_effect = mock_login
        self.uvc._login()
        assert 2 == mock_camera.call_count
        assert "host-b" == self.uvc._connect_addr

        mock_camera.reset_mock()
        self.uvc._login()
        assert mock_camera.call_count == 1
        assert mock_camera.call_args == mock.call("host-b", "admin", "seekret")
        assert mock_camera.return_value.login.call_count == 1
        assert mock_camera.return_value.login.call_args == mock.call()

    @mock.patch("uvcclient.store.get_info_store")
    @mock.patch("uvcclient.camera.UVCCameraClientV320")
    def test_login_fails_both_properly(self, mock_camera, mock_store):
        """Test if login fails properly."""
        mock_camera.return_value.login.side_effect = socket.error
        assert self.uvc._login() is None
        assert self.uvc._connect_addr is None

    def test_camera_image_tries_login_bails_on_failure(self):
        """Test retrieving failure."""
        with mock.patch.object(self.uvc, "_login") as mock_login:
            mock_login.return_value = False
            assert self.uvc.camera_image() is None
            assert mock_login.call_count == 1
            assert mock_login.call_args == mock.call()

    def test_camera_image_logged_in(self):
        """Test the login state."""
        self.uvc._camera = mock.MagicMock()
        assert self.uvc._camera.get_snapshot.return_value == self.uvc.camera_image()

    def test_camera_image_error(self):
        """Test the camera image error."""
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraConnectError
        assert self.uvc.camera_image() is None

    def test_camera_image_reauths(self):
        """Test the re-authentication."""
        responses = [0]

        def mock_snapshot():
            """Mock snapshot."""
            try:
                responses.pop()
                raise camera.CameraAuthError()
            except IndexError:
                pass
            return "image"

        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = mock_snapshot
        with mock.patch.object(self.uvc, "_login") as mock_login:
            assert "image" == self.uvc.camera_image()
            assert mock_login.call_count == 1
            assert mock_login.call_args == mock.call()
            assert [] == responses

    def test_camera_image_reauths_only_once(self):
        """Test if the re-authentication only happens once."""
        self.uvc._camera = mock.MagicMock()
        self.uvc._camera.get_snapshot.side_effect = camera.CameraAuthError
        with mock.patch.object(self.uvc, "_login") as mock_login:
            with pytest.raises(camera.CameraAuthError):
                self.uvc.camera_image()
            assert mock_login.call_count == 1
            assert mock_login.call_args == mock.call()
