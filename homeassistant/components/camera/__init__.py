"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras that can be monitored.
"""
import urllib3
import requests
import logging
import time
import math
import datetime
import re
import os
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    HTTP_NOT_FOUND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    EVENT_FTP_FILE_RECEIVED,
    STATE_MOTION_DETECTED,
    STATE_STREAMING,
    STATE_ARMED,
    STATE_ON,
    STATE_OFF,
    STATE_IDLE,
    EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE,
    ATTR_DISCOVERED,
    EVENT_STATE_CHANGED,
    ATTR_DOMAIN
    )


from homeassistant.helpers.entity_component import EntityComponent


DOMAIN = 'camera'
DEPENDENCIES = ['http', 'switch']
GROUP_NAME_ALL_CAMERAS = 'all_cameras'
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'
EVENT_CAMERA_MOTION_DETECTED = 'camera_motion_detected'
EVENT_CHILD_CALLBACK_SUFFIX = '_callback'

EVENT_CHANGE_RECORD = '_record_change'
EVENT_CHANGE_MOTION = '_motion_enabled_change'
EVENT_CHANGE_SNAPSHOT = '_snapshot_change'

EVENT_CALLBACK_RECORD = '_record_callback'
EVENT_CALLBACK_MOTION = '_motion_enabled_callback'
EVENT_CALLBACK_SNAPSHOT = '_snapshot_callback'

SWITCH_ACTION_RECORD = 'record'
SWITCH_ACTION_MOTION = 'motion_detection'
SWITCH_ACTION_SNAPSHOT = 'snapshot'

SERVICE_CAMERA = 'camera_service'

STATE_RECORDING = 'recording'

DEFAULT_RECORDING_SECONDS = 30


# The number of seconds between images before being
# considerd a new event
EVENT_GAP_THRESHOLD = 15

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}
DISCOVER_SWITCHES = "camera.switches"
ATTR_FRIENDLY_LOG_MESSAGE = "friendly_log_message"


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Track states and offer events for sensors. """

    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    for entity_id in component.entities.keys():
        entity = component.entities[entity_id]
        entity.refesh_all_settings_from_device()
        entity.add_child_component_listeners()
        # entity.update_ha_state()

        # This sets up and fired events for components that use the
        # camera as a discovery platform.

        data = {}
        data['entity_id'] = entity_id
        data[ATTR_DOMAIN] = DOMAIN
        data['name'] = entity.name + ' Record'
        data['parent_action'] = SWITCH_ACTION_RECORD
        data['callback_service'] = SERVICE_CAMERA
        data['callback_event'] = entity_id + EVENT_CALLBACK_RECORD
        data['listen_event'] = entity_id + EVENT_CHANGE_RECORD
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: DISCOVER_SWITCHES,
                       ATTR_DISCOVERED: data})

        if entity.is_motion_detection_supported:
            data = {}
            data['entity_id'] = entity_id
            data[ATTR_DOMAIN] = DOMAIN
            data['name'] = entity.name + ' Motion Detection'
            data['parent_action'] = SWITCH_ACTION_MOTION
            data['callback_event'] = entity_id + EVENT_CALLBACK_MOTION
            data['callback_service'] = SERVICE_CAMERA
            data['listen_event'] = entity_id + EVENT_CHANGE_MOTION
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                          {ATTR_SERVICE: DISCOVER_SWITCHES,
                           ATTR_DISCOVERED: data})

        data = {}
        data['entity_id'] = entity_id
        data[ATTR_DOMAIN] = DOMAIN
        data['name'] = entity.name + ' Snapshot'
        data['parent_action'] = SWITCH_ACTION_SNAPSHOT
        data['callback_service'] = SERVICE_CAMERA
        data['callback_event'] = entity_id + EVENT_CALLBACK_SNAPSHOT
        data['listen_event'] = entity_id + EVENT_CHANGE_SNAPSHOT
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: DISCOVER_SWITCHES,
                       ATTR_DISCOVERED: data})

        entity.check_for_required_configurators()

    # pylint: disable=unused-argument
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

    hass.http.register_path(
        'GET',
        re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_image,
        require_auth=True)

    # pylint: disable=unused-argument
    def _proxy_camera_mjpeg_stream(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            camera.last_connected_address = handler.address_string()
            message = "{0} started streaming to {1}".format(
                camera.name, handler.address_string())

            hass.bus.fire(
                "camera_stream_started",
                {"component": DOMAIN,
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_FRIENDLY_LOG_MESSAGE: message})

            try:
                camera.is_streaming = True
                camera.update_ha_state()

                http = urllib3.PoolManager()
                handler.request.sendall(bytes('HTTP/1.1 200 OK\r\n', 'utf-8'))
                handler.request.sendall(bytes(
                    'Content-type: multipart/x-mixed-replace; \
                        boundary=--jpgboundary\r\n\r\n', 'utf-8'))

                handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))

                while True:

                    headers = urllib3.util.make_headers(
                        basic_auth=camera.username + ':' + camera.password)

                    req = http.request(
                        'GET',
                        camera.still_image_url,
                        headers=headers)

                    headers_str = ''
                    headers_str = (
                        headers_str + 'Content-length: ' +
                        str(len(req.data)) + '\r\n')
                    headers_str = headers_str + 'Content-type: image/jpeg\r\n'
                    headers_str = headers_str + '\r\n'

                    handler.request.sendall(
                        bytes(headers_str, 'utf-8') +
                        req.data +
                        bytes('\r\n', 'utf-8'))

                    handler.request.sendall(
                        bytes('--jpgboundary\r\n', 'utf-8'))

            # This needs to be a catchall exception as we need to stop
            # streaming on any failure otherwise this will keep running
            # forever
            # pylint: disable=broad-except
            except Exception:
                camera.is_streaming = False
                camera.update_ha_state()

            message = "{0} stopped streaming to {1}".format(
                camera.name,
                handler.address_string())

            hass.bus.fire(
                "camera_stream_stopped",
                {"component": DOMAIN,
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_FRIENDLY_LOG_MESSAGE: message})

        else:
            handler.send_response(HTTP_NOT_FOUND)

        camera.is_streaming = False

    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_mjpeg_stream,
        require_auth=True)

    def _get_camera_recordings(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            offset = int(data.get('offset', 0))
            length = int(data.get('length', 10))
            rec_type = data.get('type', 'snapshot')

            rec_path = None
            if rec_type == 'snapshot':
                rec_path = camera.snapshot_images_path
            elif rec_type == 'recording':
                rec_path = camera.recording_images_path
            elif rec_type == 'motion':
                rec_path = camera.event_images_path

            data = camera.get_all_recordings(rec_path, offset, length)
            if len(data) == 0:
                handler.send_response(HTTP_NOT_FOUND)
                handler.end_headers()
            else:
                handler.write_json(data)
        else:
            handler.send_response(HTTP_NOT_FOUND)
            handler.end_headers()

    hass.http.register_path(
        'GET',
        re.compile(r'/api/camera_recordings/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _get_camera_recordings,
        require_auth=True)

    """ This creates an API endpoint that serves a saved camera image """

    def _saved_camera_image(handler, path_match, data):
        """ Get a saved camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            image_path = os.path.normpath(os.path.join(
                camera.images_path, data['image_path']))

            # Check to see that someone is not trying to do something dodgey
            # with relative paths
            if not image_path.startswith(camera.images_path):
                handler.send_response(HTTP_NOT_FOUND)

            handler.write_file(image_path)

        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path(
        'GET',
        re.compile(r'/api/saved_camera_image/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _saved_camera_image,
        require_auth=True)

    def handle_motion_detection_service(service):
        """ Handles calls to the camera services. """

        action = service.data.get('action', None)
        if action is None:
            logging.getLogger(__name__).warning(
                "Call to camera service did not specify an \
                 action in the service data")
            return

        state = service.data.get('state', None)
        if state is None:
            logging.getLogger(__name__).warning(
                "Call to camera service did not specify a \
                 state in the service data")
            return

        target_cameras = component.extract_from_service(service)

        for camera in target_cameras:
            if action == SWITCH_ACTION_MOTION:
                if (state == STATE_ON and not
                        camera.is_motion_detection_enabled):
                    camera.enable_motion_detection()
                elif (state == STATE_OFF and
                        camera.is_motion_detection_enabled):
                    camera.disable_motion_detection()

            elif action == SWITCH_ACTION_RECORD:
                if (state == STATE_ON and not
                        camera.is_recording):
                    camera.record_stream()
                elif (state == STATE_OFF and
                        camera.is_recording):
                    camera.stop_recording()

            elif action == SWITCH_ACTION_SNAPSHOT:
                if (state == STATE_ON and not
                        camera.is_taking_snapshot):
                    camera.take_snapshot()

            camera.update_ha_state(True)

    hass.services.register(
        DOMAIN,
        SERVICE_CAMERA,
        handle_motion_detection_service)

    return True


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods
class Camera(Entity):
    """ Base class for cameras. """

    def __init__(self, hass, device_info):
        self.hass = hass
        self.device_info = device_info
        self.base_url = device_info.get('base_url')
        if not self.base_url.endswith('/'):
            self.base_url = self.base_url + '/'
        self.username = device_info.get('username')
        self.password = device_info.get('password')
        self.is_streaming = False
        self._is_detecting_motion = False
        self._last_motion_detected = datetime.datetime.now()
        self.last_connected_address = None
        self._still_image_url = device_info.get('still_image_url', 'image.jpg')
        # these are the camera functions and capabilities initialised
        # to defaults, these should be overridden in derived classes
        self._is_motion_detection_supported = False
        self._is_motion_detection_enabled = False

        self._is_recording = False
        self._is_taking_snapshot = False

        self._is_ftp_upload_supported = False
        self._is_ftp_upload_enabled = False
        self._can_auto_configure_ftp = False

        self._is_ftp_configured = False
        self._ftp_host = ''
        self._ftp_port = 21
        self._ftp_username = ''
        self._ftp_password = ''
        self._ftp_relative_path = ''

        self._logger = logging.getLogger(__name__)

        self._images_path = device_info.get('images_path', None)

        if (self._images_path is not None and not
                os.path.isdir(self._images_path)):
            os.makedirs(self._images_path)

        self._event_images_path = None
        self._recording_images_path = None
        self._snapshot_images_path = None
        self._ftp_path = None

        self._child_entities = {}

        self._action_entities = {}

        self._ftp_configurator = None

        self._lastconfig_update_from_device = None

        self.hass.bus.listen(
            EVENT_FTP_FILE_RECEIVED,
            self.process_file_event)

    def add_child_component_listeners(self):
        self.hass.bus.listen(
            self.entity_id + EVENT_CALLBACK_MOTION,
            self.process_motion_switch_creation)

        self.hass.bus.listen(
            self.entity_id + EVENT_CALLBACK_RECORD,
            self.process_child_switch_creation)

        self.hass.bus.listen(
            self.entity_id + EVENT_CALLBACK_SNAPSHOT,
            self.process_child_switch_creation)

    def process_motion_switch_creation(self, event):
        """ Called when a child motion detection switch is created """
        self.process_child_switch_creation(event)
        self.send_motion_state()

    def process_child_switch_creation(self, event):
        """ Called when a child switch is created """
        if not event or not event.data:
            return

        child_entity_id = event.data.get('entity_id')
        entity_action = event.data.get('parent_action')
        self._action_entities[entity_action] = child_entity_id

        self._logger.info(
            'Registerd child switch {0} for {1} on {2}'.format(
                child_entity_id,
                entity_action,
                self.entity_id))


    def send_motion_state(self):
        """ Sends an event notifying listeners of the motion
        detection state """
        state = STATE_OFF
        if self.is_motion_detection_enabled:
            state = STATE_ON

        self.hass.bus.fire(
            self.entity_id + EVENT_CHANGE_MOTION,
            {
                'entity_id': self.entity_id,
                'state': state
            })

    def send_recording_state(self):
        """ Sends an event notifying listeners of the
        recording state """
        state = STATE_OFF
        if self.is_recording:
            state = STATE_ON

        self.hass.bus.fire(
            self.entity_id + EVENT_CHANGE_RECORD,
            {
                'entity_id': self.entity_id,
                'state': state
            })

    def send_snapshot_state(self):
        """ Sends an event notifying listeners of the
        snapshot state """
        state = STATE_OFF
        if self.is_taking_snapshot:
            state = STATE_ON

        self.hass.bus.fire(
            self.entity_id + EVENT_CHANGE_SNAPSHOT,
            {
                'entity_id': self.entity_id,
                'state': state
            })

    def update(self):
        """ Retrieve latest state. """
        self.refesh_all_settings_from_device()
        self.send_motion_state()

    def refesh_all_settings_from_device(self):
        """ A stub methos that should be overridden in derived classes to
            fetch the settings from the camera. """
        pass

    def get_camera_image(self, stream=False):
        """ Return a still image reponse from the camera """
        response = requests.get(
            self.still_image_url,
            auth=(self.username, self.password), stream=stream)

        return response

    @property
    def name(self):
        """ Return the name of this device """
        if self.device_info.get('name'):
            return self.device_info.get('name')
        else:
            return super().name

    @property
    def state(self):
        """ Returns the state of the entity. """
        seconds_since_last_motion = (
            datetime.datetime.now() -
            self._last_motion_detected).total_seconds()

        if (self._is_detecting_motion and
                seconds_since_last_motion > EVENT_GAP_THRESHOLD):
            self._is_detecting_motion = False

        if self._is_detecting_motion:
            return STATE_MOTION_DETECTED
        elif self.is_recording:
            return STATE_RECORDING
        elif self.is_streaming:
            return STATE_STREAMING
        elif self._is_motion_detection_enabled:
            return STATE_ARMED
        else:
            return STATE_IDLE

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes
        attr['model_name'] = self.device_info.get('model', 'generic')
        attr['brand'] = self.device_info.get('brand', 'generic')
        attr['still_image_url'] = '/api/camera_proxy/' + self.entity_id
        attr[ATTR_ENTITY_PICTURE] = (
            '/api/camera_proxy/' +
            self.entity_id + '?time=' +
            str(time.time()))
        attr['stream_url'] = '/api/camera_proxy_stream/' + self.entity_id
        motion_time = self._last_motion_detected.strftime('%Y-%m-%d %H-%M-%S')
        attr['last_motion_time'] = motion_time
        attr['last_connected_address'] = self.last_connected_address
        attr['child_entities'] = self._action_entities
        attr['is_recording'] = self._is_recording
        attr['is_taking_snapshot'] = self.is_taking_snapshot

        attr.update(self.function_attributes)

        return attr

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        return self.base_url + self._still_image_url

    def enable_motion_detection(self):
        """ Enable the motion detection settings for the camera.
            This should be overridden in derived classes """
        if not self.is_motion_detection_supported:
            return False
        if self.is_motion_detection_enabled:
            return True

    def disable_motion_detection(self):
        """ Disable the motion detection settings for the camera.
            This should be overridden in derived classes """
        if not self.is_motion_detection_supported:
            return False
        if self.is_motion_detection_enabled:
            return True

    def set_ftp_details(self):
        """ A stub method that should be overridden in base classes
        to set the FTP configuration values for the specific device. """
        if not self.is_motion_detection_supported:
            return False

    def process_file_event(self, event):
        """ Event handler for a new FTP upload event from the FTP component.
            It checks the new file's path against the configured FTP directory
            to determine whether or not to process the file """
        if self.ftp_path is not None:
            if event.data.get('file_name').startswith(self.ftp_path):
                if self._is_detecting_motion is False:
                    self._is_detecting_motion = True
                    self.update_ha_state()

                self._last_motion_detected = datetime.datetime.now()
                self.process_new_file(event.data.get('file_name'))

    def process_new_file(self, path):
        """ Used to process a new motion capture image, it finds the most
        recently created event directory and moves the file there in order
        to group all images captured as part of the same event together.
        If the image is the first in the sequence a new directory will be
        created. """
        if not os.path.isfile(path):
            return False

        if self.event_images_path is None:
            return False

        if not os.path.isdir(self.event_images_path):
            os.makedirs(self.event_images_path)

        all_subdirs = [
            d for d in os.listdir(self.event_images_path)
            if (os.path.isdir(os.path.join(self.event_images_path, d)) and
                d.startswith('recording-'))]

        event_dir = None
        if len(all_subdirs) > 0:
            event_dir = sorted(
                all_subdirs,
                key=lambda x: os.path.getctime(
                    os.path.join(self.event_images_path, x)),
                reverse=True)[:1][0]

            event_dir = os.path.join(self.event_images_path, event_dir)
            file_dt = datetime.datetime.fromtimestamp(os.path.getctime(path))

            # Get the newest file in the dir
            all_subfiles = [
                f for f in os.listdir(event_dir)
                if (os.path.isfile(os.path.join(event_dir, f)) and
                    f.startswith('recording_image-'))]

            if len(all_subfiles) > 0:
                newest_image = sorted(
                    all_subfiles,
                    key=lambda x: os.path.getctime(os.path.join(event_dir, x)),
                    reverse=True)[:1][0]

                newest_image_path = os.path.join(event_dir, newest_image)
                newest_file_dt = datetime.datetime.fromtimestamp(
                    os.path.getctime(newest_image_path))

                if ((file_dt - newest_file_dt)
                        .total_seconds() > EVENT_GAP_THRESHOLD):
                    event_dir = None
            else:
                event_dir_dt = datetime.datetime.fromtimestamp(
                    os.path.getctime(event_dir))

                if ((file_dt - event_dir_dt)
                        .total_seconds() > EVENT_GAP_THRESHOLD):
                    event_dir = None

        if event_dir is None:
            new_event_dir_name = 'recording-' + datetime.datetime.fromtimestamp(
                os.path.getctime(path)).strftime('%Y-%m-%d_%H-%M-%S')

            event_dir = os.path.join(
                self.event_images_path,
                new_event_dir_name)

            if not os.path.isdir(event_dir):
                os.makedirs(event_dir)

            self.hass.bus.fire(
                EVENT_CAMERA_MOTION_DETECTED,
                {"component": DOMAIN,
                    ATTR_ENTITY_ID: self.entity_id,
                    'event_images_path': event_dir,
                    'event_images_dir': new_event_dir_name})

        new_file_name = 'recording_image-' + datetime.datetime.fromtimestamp(
            os.path.getctime(path)).strftime('%Y-%m-%d_%H-%M-%S-%f') + '.jpg'
        new_file_path = os.path.join(event_dir, new_file_name)

        if not os.path.isfile(path):
            return False

        os.rename(path, new_file_path)

        return True

    # pylint: disable=too-many-locals
    def get_all_recordings(self, recording_path, start=0, length=10):
        """ Looks on the file system for saved camera recordings such as motion
        detection or user initiated recordings.  The are returned in
        chronological order """

        events_data = []
        if not os.path.isdir(recording_path):
            return events_data

        base_path = os.path.basename(os.path.normpath(recording_path))

        all_subdirs = [
            d for d in os.listdir(recording_path)
            if (os.path.isdir(os.path.join(recording_path, d)) and
                d.startswith('recording-'))]

        event_dirs = sorted(
            all_subdirs,
            key=lambda x: os.path.getctime(
                os.path.join(recording_path, x)),
            reverse=True)

        count = 0
        for event_dir in event_dirs:
            if count < start:
                count += 1
                continue
            if count >= start + length:
                break
            event_data = {}
            event_data['directory'] = event_dir
            event_data['name'] = event_dir
            event_data['fullPath'] = os.path.join(
                recording_path,
                event_dir)
            event_data['thumbUrl'] = ''
            event_data['images'] = []
            event_data['time'] = datetime.datetime.fromtimestamp(
                os.path.getctime(
                    event_data['fullPath'])).strftime('%Y-%m-%d %H:%M:%S')

            all_subfiles = [
                f for f in os.listdir(event_data['fullPath'])
                if (os.path.isfile(os.path.join(event_data['fullPath'], f)) and
                    f.startswith('recording_image-'))]

            all_subfiles = sorted(
                all_subfiles,
                key=lambda x: os.path.getctime(
                    os.path.join(event_data['fullPath'], x)),
                reverse=False)

            for image_file in all_subfiles:
                full_image_path = os.path.join(
                    event_data['fullPath'],
                    image_file)

                image_data = {}
                image_data['fileName'] = image_file
                image_data['path'] = (
                    base_path +
                    os.path.sep +
                    event_dir +
                    os.path.sep +
                    image_file)

                image_data['url'] = (
                    'api/saved_camera_image/' +
                    self.entity_id +
                    '?image_path=' +
                    image_data['path'])

                image_data['time'] = datetime.datetime.fromtimestamp(
                    os.path.getctime(
                        full_image_path)).strftime('%Y-%m-%d %H:%M:%S')
                event_data['images'].append(image_data)

            if len(event_data['images']) > 0:
                thumb_index = math.floor(len(event_data['images'])/2)
                event_data['thumbUrl'] = (
                    event_data['images'][thumb_index]['url'])

            events_data.append(event_data)
            count += 1

        return events_data


    def record_stream(self):
        """ Records individual frames to disk for a period of time """
        if self.is_recording:
            return
        else:
            self._is_recording = True

        self.update_ha_state(True)
        self.send_recording_state()

        rec_dir = ('recording-' +
            datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))

        rec_dir_full = os.path.join(self.recording_images_path, rec_dir)

        if not os.path.isdir(rec_dir_full):
            os.makedirs(rec_dir_full)

        recording_length = DEFAULT_RECORDING_SECONDS
        recording_started = datetime.datetime.now()
        recording_time = 0
        while (recording_time < recording_length
                and self._is_recording):

            new_file_name = (
                'recording_image-' +
                datetime.datetime.now().strftime(
                    '%Y-%m-%d_%H-%M-%S-%f') + '.jpg')

            new_file_path = os.path.join(rec_dir_full, new_file_name)

            response = self.get_camera_image()
            open(new_file_path, 'wb').write(response.content)

            recording_time = (
                datetime.datetime.now() - recording_started).total_seconds()

        self._is_recording = False
        self.update_ha_state(True)
        self.send_recording_state()

    def stop_recording(self):
        """ Stop recording camera stream """
        self._is_recording = False

    def take_snapshot(self):
        """ Records individual frames to disk for a period of time """
        if self.is_taking_snapshot:
            return
        else:
            self._is_taking_snapshot = True

        self.send_snapshot_state()

        time_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        rec_dir = ('recording-' + time_str)

        rec_dir_full = os.path.join(self.snapshot_images_path, rec_dir)

        if not os.path.isdir(rec_dir_full):
            os.makedirs(rec_dir_full)

        new_file_name = ('recording_image-' + time_str + '.jpg')

        new_file_path = os.path.join(rec_dir_full, new_file_name)

        response = self.get_camera_image()
        open(new_file_path, 'wb').write(response.content)

        self._is_taking_snapshot = False
        self.update_ha_state()
        self.send_snapshot_state()

    @property
    def images_path(self):
        """ The base path for the location of images such as snapshots,
            recordings and motion capture events """
        if self._images_path is None:
            default_images_path = os.path.join(
                self.hass.config.config_dir,
                'camera_data')

            default_images_path = os.path.join(
                default_images_path,
                self.entity_id)

            self._images_path = default_images_path

            if not os.path.isdir(self.images_path):
                os.makedirs(self.images_path)

        return self._images_path

    @property
    def event_images_path(self):
        """ The base path for the location of motion capture images """
        if self.images_path is None:
            return None

        if self._event_images_path is None:
            self._event_images_path = os.path.join(
                self.images_path, 'events')

        return self._event_images_path

    @property
    def recording_images_path(self):
        """ The base path for the location of recording images """
        if self.images_path is None:
            return None

        if self._recording_images_path is None:
            self._recording_images_path = os.path.join(
                self.images_path, 'recordings')

        return self._recording_images_path

    @property
    def snapshot_images_path(self):
        """ The base path for the location of snapshot images """
        if self.images_path is None:
            return None

        if self._snapshot_images_path is None:
            self._snapshot_images_path = os.path.join(
                self.images_path, 'snapshot')

        return self._snapshot_images_path

    @property
    def ftp_path(self):
        """ Gets the path on the local filesystem where uploaded motion captured
            images from this device are stored """
        if self._ftp_path is None:
            ftp_comp = get_component('ftp')
            if ftp_comp is not None and ftp_comp.FTP_SERVER is not None:
                self._ftp_path = os.path.join(
                    ftp_comp.FTP_SERVER.ftp_root_path,
                    self.entity_id)

        return self._ftp_path

    @property
    def is_motion_detection_supported(self):
        """ Returns true if this device supports motion detection """
        return self._is_motion_detection_supported

    @property
    def is_motion_detection_enabled(self):
        """ Returns true if motion detection is currently enabled """
        return self._is_motion_detection_enabled

    @property
    def is_recording(self):
        """ Returns true the device is recording """
        return self._is_recording

    @property
    def is_taking_snapshot(self):
        """ Returns true the device is currently taking a snapshot """
        return self._is_taking_snapshot

    @property
    def is_ftp_upload_supported(self):
        """ Returns true the device supports uploading motion
        capture frames via FTP """
        return self._is_ftp_upload_supported

    @property
    def is_ftp_upload_enabled(self):
        """ Returns true uploading motion capture frames is
        enabled on the device """
        return self._is_ftp_upload_enabled

    @property
    def is_ftp_configured(self):
        """ Returns true the device has FTP settings configured """
        return self._is_ftp_configured

    @property
    def function_attributes(self):
        """ Returns a dictioanry containing information about the
            camera's functionality """
        attr = {}
        attr['is_motion_detection_supported'] = (
            self.is_motion_detection_supported)
        attr['is_motion_detection_enabled'] = self.is_motion_detection_enabled
        attr['is_ftp_upload_supported'] = self.is_ftp_upload_supported
        attr['is_ftp_upload_enabled'] = self.is_ftp_upload_enabled
        attr['is_ftp_configured'] = self.is_ftp_configured
        return attr

    def check_ftp_settings(self):
        """ This comapres the FTP settings stored on the
        device against the expected values """
        ftp_server = get_component('ftp').FTP_SERVER

        if ftp_server is None:
            return False

        if self._ftp_host != ftp_server.server_ip:
            return False
        if self._ftp_port != str(ftp_server.server_port):
            return False
        if self._ftp_username != ftp_server.username:
            return False
        if self._ftp_password != ftp_server.password:
            return False
        if self._ftp_relative_path != self.entity_id:
            return False

        return True

    def check_for_required_configurators(self):
        """ Launches any common camera configurators based on capabilities """
        if (self.is_motion_detection_supported and
                not self.is_ftp_configured):
            self.request_ftp_configuration()

    def request_ftp_configuration(self):
        """ Request configuration steps from the user. """

        configurator = get_component('configurator')

        # self._is_ftp_configured = self.check_ftp_settings()
        # if self._is_ftp_configured:
        #     if self._ftp_configurator is not None:
        #         configurator.request_done(self._ftp_configurator)
        #         self._ftp_configurator = None
        #     return

        if self._ftp_configurator is not None:
            return

        if self.entity_id is None:
            return

        def camera_configuration_callback(data):
            """ Actions to do when our configuration callback is called. """
            if self._ftp_configurator is None:
                return

            if self._can_auto_configure_ftp:
                self.set_ftp_details()
            else:
                self.refesh_all_settings_from_device()

            self._is_ftp_configured = self.check_ftp_settings()

            configurator = get_component('configurator')
            if self._is_ftp_configured:
                configurator.request_done(self._ftp_configurator)
                self._ftp_configurator = None
            else:
                configurator.notify_errors(
                    self._ftp_configurator,
                    "Failed to set FTP values, please try again \
                        and check the logs for info.")

        paragraphs = []
        paragraphs.append('The current FTP settings are:' +
            '\nHost:{0}'.format(self._ftp_host) +
            '\nPort:{0}'.format(self._ftp_port) +
            '\nUsername:{0}'.format(self._ftp_username) +
            '\nPassword:{0}'.format('*********'))

        ftp_server = get_component('ftp').FTP_SERVER

        if ftp_server is None:
            return

        paragraphs.append('They should be set to the following:' +
            '\nHost:{0}'.format(ftp_server.server_ip) +
            '\nPort:{0}'.format(ftp_server.server_port) +
            '\nUsername:{0}'.format(ftp_server.username) +
            '\nPassword:{0}'.format(ftp_server.password) +
            '\nPath:{0}'.format(self.entity_id))

        btn_text = 'I have configured my device'
        if self._can_auto_configure_ftp:
            paragraphs.append('This device supports automatically configuring' +
                ' these values.  Click the button below to configure them now.')
            btn_text = 'Configure Automatically'
        else:
            paragraphs.append('This device does not support automatic FTP' +
                ' configuration.  You will need to log into your device and' +
                ' manually set them.')

        self._ftp_configurator = configurator.request_config(
            self.hass, self.name + ' FTP', camera_configuration_callback,
            description=("Your camera supports motion detection "
                        "notifications via FTP but the settings on "
                        "your camera don't seem to be configured correctly."),
            # description_image="/static/images/config_philips_hue.jpg",
            submit_caption=btn_text,
            paragraphs=paragraphs
        )

        # _CONFIGURING[host] = configurator.request_config(
        #     hass, "Philips Hue", camera_configuration_callback,
        #     description=("Press the button on the bridge to register Philips Hue "
        #                  "with Home Assistant."),
        #     description_image="/static/images/config_philips_hue.jpg",
        #     submit_caption="I have pressed the button"
        #)
