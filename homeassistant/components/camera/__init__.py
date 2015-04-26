"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras that can be monitored.
"""
import urllib3
import mimetypes
import requests
import logging
import time
from homeassistant.helpers.entity import Entity
import time
import datetime
from datetime import timedelta
import re
import os
from homeassistant.loader import get_component
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    HTTP_NOT_FOUND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    EVENT_FTP_FILE_RECEIVED,
    EVENT_COMPONENT_LOADED
    )


from homeassistant.helpers.entity_component import EntityComponent


DOMAIN = 'camera'
DEPENDENCIES = ['http']
GROUP_NAME_ALL_CAMERAS = 'all_cameras'
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'
EVENT_CAMERA_MOTION_DETECTED = 'camera_motion_detected'

# The number of seconds between images before being
# considerd a new event
EVENT_GAP_THRESHOLD = 15

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}
ATTR_FRIENDLY_LOG_MESSAGE = "friendly_log_message"


def setup(hass, config):
    """ Track states and offer events for sensors. """

    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)


    def _proxy_camera_image(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            response = camera.get_camera_image()
            handler.wfile.write(response.content)
        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path('GET', re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_image, require_auth=True)


    def _proxy_camera_mjpeg_stream(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            message = "{0} started streaming to {1}".format(camera.name, handler.address_string())
            hass.bus.fire(
                "camera_stream_started", {"component": DOMAIN,
                ATTR_ENTITY_ID: entity_id,
                ATTR_FRIENDLY_LOG_MESSAGE: message})

            try:
                camera.is_streaming = True
                camera.update_ha_state()


                http = urllib3.PoolManager()
                handler.request.sendall(bytes('HTTP/1.1 200 OK\r\n', 'utf-8'))
                handler.request.sendall(bytes('Content-type: multipart/x-mixed-replace; boundary=--jpgboundary\r\n\r\n', 'utf-8'))
                handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))
                count = 0
                while True:

                    headers = urllib3.util.make_headers(basic_auth=camera.username + ':' + camera.password)
                    req = http.request('GET', camera.still_image_url, headers = headers)

                    headersStr = ''
                    headersStr = headersStr + 'Content-length: ' + str(len(req.data)) + '\r\n'
                    headersStr = headersStr + 'Content-type: image/jpeg\r\n'
                    headersStr = headersStr + '\r\n'

                    handler.request.sendall(bytes(headersStr, 'utf-8') + req.data + bytes('\r\n', 'utf-8'))
                    handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))
            except Exception:
                camera.is_streaming = False
                camera.update_ha_state()

            message = "{0} stopped streaming to {1}".format(camera.name, handler.address_string())
            hass.bus.fire(
                "camera_stream_stopped", {"component": DOMAIN,
                ATTR_ENTITY_ID: entity_id,
                ATTR_FRIENDLY_LOG_MESSAGE: message})

        else:
            handler.send_response(HTTP_NOT_FOUND)

        camera.is_streaming = False

    hass.http.register_path('GET', re.compile(r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_mjpeg_stream, require_auth=True)

    def handle_motion_detection_service(service):
        """ Handles calls to the camera services. """
        target_cameras = component.extract_from_service(service)
        feature_name = service.data.get('feature', 'motion_detection')
        for camera in target_cameras:
            if feature_name == 'configure_ftp':
                if service.service == SERVICE_TURN_ON:
                    camera.set_ftp_details()
            else:
                if service.service == SERVICE_TURN_ON:
                    camera.enable_motion_detection()
                else:
                    camera.disable_motion_detection()

            camera.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_motion_detection_service)
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_motion_detection_service)

    return True



class Camera(Entity):
    """ Base class for cameras. """

    def __init__(self, hass, device_info):
        #super().__init__(hass, device_info)
        self.hass = hass
        self.device_info = device_info
        self.BASE_URL = device_info.get('base_url')
        if not self.BASE_URL.endswith('/'):
            self.BASE_URL = self.BASE_URL + '/'
        self.username = device_info.get('username')
        self.password = device_info.get('password')
        self.is_streaming = False
        # these are the camera functions and capabilities initialised
        # to defaults, these should be overridden in derived classes
        self._is_motion_detection_supported = False
        self._is_motion_detection_enabled = False

        self._is_ftp_upload_supported = False
        self._is_ftp_upload_enabled = False

        self._is_ftp_configured = False
        self._ftp_host = ''
        self._ftp_port = 21
        self._ftp_username = ''
        self._ftp_password = ''

        self._images_path = device_info.get('images_path', None)

        if self._images_path != None and not os.path.isdir(self._images_path):
            os.makedirs(self._images_path)

        self._event_images_path = None
        self._ftp_path = None

        self.hass.bus.listen(
            EVENT_FTP_FILE_RECEIVED,
            self.process_file_event)

        # self.hass.bus.listen_once(
        #     EVENT_COMPONENT_LOADED,
        #     self.ftp_server_loaded_event)



    def get_camera_image(self, stream=False):
        response = requests.get(self.still_image_url, auth=(self.username, self.password), stream=stream)
        return response

    @property
    def name(self):
        if self.device_info.get('name'):
            return self.device_info.get('name')
        else:
            return super().name

    @property
    def state(self):
        """ Returns the state of the entity. """
        if self.is_streaming:
            return "Streaming"
        else:
            return "Idle"


    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes
        attr['model_name'] = self.device_info.get('model', 'generic')
        attr['brand'] = self.device_info.get('brand', 'generic')
        attr['still_image_url'] = '/api/camera_proxy/' + self.entity_id
        attr[ATTR_ENTITY_PICTURE] = '/api/camera_proxy/' + self.entity_id + '?api_password=' + self.hass.http.api_password + '&time=' + str(time.time())
        attr['stream_url'] = '/api/camera_proxy_stream/' + self.entity_id

        attr.update(self.function_attributes)

        return attr

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        if self.device_info.get('still_image_url'):
            return self.BASE_URL + self.device_info.get('still_image_url')
        return self.BASE_URL + 'image.jpg'

    def enable_motion_detection(self):
        if not self.is_motion_detection_supported:
            return False
        if self.is_motion_detection_enabled:
            return True

    def disable_motion_detection(self):
        if not self.is_motion_detection_supported:
            return False
        if self.is_motion_detection_enabled:
            return True

    def set_ftp_details(self):
        if not self.is_motion_detection_supported:
            return False

    def process_file_event(self, event):
        if self.ftp_path != None:
            if event.data.get('file_name').startswith(self.ftp_path):
                self.process_new_file(event.data.get('file_name'))

    def process_new_file(self, path):
        if not os.path.isfile(path):
            return False

        if self.event_images_path == None:
            return False

        if not os.path.isdir(self.event_images_path):
            os.makedirs(self.event_images_path)

        all_subdirs = [d for d in os.listdir(self.event_images_path)
            if os.path.isdir(os.path.join(self.event_images_path, d)) and d.startswith('event-')]

        event_dir = None
        if len(all_subdirs) > 0:
            event_dir = sorted(all_subdirs, key=lambda x: os.path.getctime(os.path.join(self.event_images_path, x)), reverse=True)[:1][0]
            event_dir = os.path.join(self.event_images_path, event_dir)
            file_dt = datetime.datetime.fromtimestamp(os.path.getctime(path))

            # Get the newest file in the dir
            all_subfiles = [f for f in os.listdir(event_dir)
                if os.path.isfile(os.path.join(event_dir, f)) and f.startswith('event_image-')]

            if len(all_subfiles) > 0:
                newest_image = sorted(all_subfiles, key=lambda x: os.path.getctime(os.path.join(event_dir, x)), reverse=True)[:1][0]
                newest_image_path = os.path.join(event_dir, newest_image)
                newest_file_dt = datetime.datetime.fromtimestamp(os.path.getctime(newest_image_path))
                if (file_dt - newest_file_dt).total_seconds() > EVENT_GAP_THRESHOLD:
                    event_dir = None
            else:
                event_dir_dt = datetime.datetime.fromtimestamp(os.path.getctime(event_dir))
                if (file_dt - event_dir_dt).total_seconds() > EVENT_GAP_THRESHOLD:
                    event_dir = None


        if event_dir == None:
            new_event_dir_name = 'event-' + datetime.datetime.fromtimestamp(os.path.getctime(path)).strftime('%Y-%m-%d_%H-%M-%S')
            event_dir = os.path.join(self.event_images_path, new_event_dir_name)
            if not os.path.isdir(event_dir):
                os.makedirs(event_dir)

            self.hass.bus.fire(
                EVENT_CAMERA_MOTION_DETECTED, {"component": DOMAIN,
                ATTR_ENTITY_ID: self.entity_id,
                'event_images_path': event_dir,
                'event_images_dir': new_event_dir_name})

        new_file_name = 'event_image-' + datetime.datetime.fromtimestamp(os.path.getctime(path)).strftime('%Y-%m-%d_%H-%M-%S-%f') + '.jpg'
        new_file_path = os.path.join(event_dir, new_file_name)

        if not os.path.isfile(path):
            return False

        os.rename(path, new_file_path)

        return True


    @property
    def images_path(self):
        if self._images_path == None:
            default_images_path = os.path.join(self.hass.config.config_dir, 'camera_data')
            default_images_path = os.path.join(default_images_path, self.entity_id)
            self._images_path = default_images_path

            if not os.path.isdir(self.images_path):
                os.makedirs(self.images_path)

        return self._images_path

    @property
    def event_images_path(self):
        if self.images_path == None:
            return None

        if self._event_images_path == None:
           self._event_images_path = os.path.join(self.images_path, 'events')

        return self._event_images_path

    @property
    def ftp_path(self):
        if self._ftp_path == None:
            ftp_comp = get_component('ftp')
            if ftp_comp != None and ftp_comp.ftp_server != None:
                self._ftp_path = os.path.join(ftp_comp.ftp_server.ftp_root_path, self.entity_id)
        return self._ftp_path

    @property
    def is_motion_detection_supported(self):
        return self._is_motion_detection_supported

    @property
    def is_motion_detection_enabled(self):
        return self._is_motion_detection_enabled

    @property
    def is_ftp_upload_supported(self):
        return self._is_ftp_upload_supported

    @property
    def is_ftp_upload_enabled(self):
        return self._is_ftp_upload_enabled

    @property
    def is_ftp_configured(self):
        return self._is_ftp_configured

    @property
    def function_attributes(self):
        attr = {}
        attr['is_motion_detection_supported'] = self.is_motion_detection_supported
        attr['is_motion_detection_enabled'] = self.is_motion_detection_enabled
        attr['is_ftp_upload_supported'] = self.is_ftp_upload_supported
        attr['is_ftp_upload_enabled'] = self.is_ftp_upload_enabled
        attr['is_ftp_configured'] = self.is_ftp_configured
        return attr
