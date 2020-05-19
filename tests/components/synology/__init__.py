"""Tests for the Synology component."""
import requests

from homeassistant.components.synology.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERITY_SSL,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.async_mock import MagicMock, patch

NAME = DEFAULT_NAME
HOST = "0.0.0.0"
PORT = DEFAULT_PORT
SSL = DEFAULT_SSL
URL = f"{'https' if SSL else 'http'}://{HOST}:{PORT}"
VERIFY_SSL = DEFAULT_VERITY_SSL
USERNAME = "username"
PASSWORD = "password"
TIMEOUT = DEFAULT_TIMEOUT

CONF_FLOW = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_TIMEOUT: TIMEOUT,
}

CONF_ENTRY = {
    CONF_NAME: NAME,
    CONF_URL: URL,
    CONF_VERIFY_SSL: VERIFY_SSL,
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_TIMEOUT: TIMEOUT,
}

CAMERA1_ID = "1"
CAMERA1_NAME = "camera1"
CAMERA1_ENTITY_ID = "camera.camera1"
CAMERA2_ID = "2"
CAMERA2_NAME = "camera2"
CAMERA2_ENTITY_ID = "camera.camera2"


def _mocked_camera(camera_id: str, name: str):
    camera = MagicMock()
    camera.camera_id = camera_id
    camera.name = name
    camera.is_recording = True
    camera.is_enabled = True
    return camera


def _mocked_motion_setting(camera_id: str):
    motion_setting = MagicMock()
    motion_setting.is_enabled = True
    return motion_setting


def _mocked_device(*args, **kwargs):
    device = MagicMock()
    camera1 = _mocked_camera(CAMERA1_ID, CAMERA1_NAME)
    camera2 = _mocked_camera(CAMERA2_ID, CAMERA2_NAME)
    cameras = {
        CAMERA1_ID: camera1,
        CAMERA2_ID: camera2,
    }
    type(device).get_all_cameras = MagicMock(return_value=[camera1, camera2])

    type(device).update = MagicMock()
    type(device).get_camera = MagicMock(
        side_effect=lambda camera_id: cameras[camera_id]
    )
    type(device).get_motion_setting = MagicMock(side_effect=_mocked_motion_setting)

    return device


def _patch_device(target: str, raise_exception: bool):
    return patch(
        target,
        side_effect=requests.exceptions.RequestException
        if raise_exception
        else _mocked_device,
    )


def _patch_config_flow_device(raise_exception: bool = False):
    return _patch_device(
        "homeassistant.components.synology.config_flow.SurveillanceStation",
        raise_exception,
    )


def _patch_camera_device(raise_exception: bool = False):
    return _patch_device(
        "homeassistant.components.synology.camera.SurveillanceStation", raise_exception
    )
