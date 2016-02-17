"""
homeassistant.components.camera.uvc
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Ubiquiti's UVC cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.uvc/
"""
import logging
import socket

import requests

from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN, Camera

REQUIREMENTS = ['uvcclient==0.6']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Discover cameras on a Unifi NVR. """
    if not validate_config({DOMAIN: config}, {DOMAIN: ['nvr', 'key']},
                           _LOGGER):
        return None

    addr = config.get('nvr')
    port = int(config.get('port', 7080))
    key = config.get('key')

    from uvcclient import nvr
    nvrconn = nvr.UVCRemote(addr, port, key)
    try:
        cameras = nvrconn.index()
    except nvr.NotAuthorized:
        _LOGGER.error('Authorization failure while connecting to NVR')
        return False
    except nvr.NvrError:
        _LOGGER.error('NVR refuses to talk to me')
        return False
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to NVR: %s', str(ex))
        return False

    for camera in cameras:
        add_devices([UnifiVideoCamera(nvrconn,
                                      camera['uuid'],
                                      camera['name'])])


class UnifiVideoCamera(Camera):
    """ A Ubiquiti Unifi Video Camera. """

    def __init__(self, nvr, uuid, name):
        super(UnifiVideoCamera, self).__init__()
        self._nvr = nvr
        self._uuid = uuid
        self._name = name
        self.is_streaming = False
        self._connect_addr = None
        self._camera = None

    @property
    def name(self):
        return self._name

    @property
    def is_recording(self):
        caminfo = self._nvr.get_camera(self._uuid)
        return caminfo['recordingSettings']['fullTimeRecordEnabled']

    @property
    def brand(self):
        return 'Ubiquiti'

    @property
    def model(self):
        caminfo = self._nvr.get_camera(self._uuid)
        return caminfo['model']

    def _login(self):
        from uvcclient import camera as uvc_camera
        caminfo = self._nvr.get_camera(self._uuid)
        if self._connect_addr:
            addrs = [self._connect_addr]
        else:
            addrs = [caminfo['host'], caminfo['internalHost']]

        camera = None
        for addr in addrs:
            try:
                camera = uvc_camera.UVCCameraClient(addr,
                                                    caminfo['username'],
                                                    'ubnt')
                camera.login()
                _LOGGER.debug('Logged into UVC camera %(name)s via %(addr)s',
                              dict(name=self._name, addr=addr))
                self._connect_addr = addr
            except socket.error:
                pass
            except uvc_camera.CameraConnectError:
                pass
            except uvc_camera.CameraAuthError:
                pass
        if not camera:
            _LOGGER.error('Unable to login to camera')
            return None

        self._camera = camera
        return True

    def camera_image(self):
        from uvcclient import camera as uvc_camera
        if not self._camera:
            if not self._login():
                return

        def _get_image(retry=True):
            try:
                return self._camera.get_snapshot()
            except uvc_camera.CameraConnectError:
                _LOGGER.error('Unable to contact camera')
            except uvc_camera.CameraAuthError:
                if retry:
                    self._login()
                    return _get_image(retry=False)
                else:
                    _LOGGER.error('Unable to log into camera, unable '
                                  'to get snapshot')
                    raise

        return _get_image()
