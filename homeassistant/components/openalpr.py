"""
Component that will help set the openalpr for video streams.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/openalpr/
"""
from base64 import b64encode
import logging
import os
from time import time

import requests
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.components.ffmpeg import (
    get_binary, run_test, CONF_INPUT, CONF_EXTRA_ARGUMENTS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'openalpr'
DEPENDENCIES = ['ffmpeg']
REQUIREMENTS = [
    'https://github.com/pvizeli/cloudapi/releases/download/1.0.2/'
    'python-1.0.2.zip#cloud_api==1.0.2',
    'ha-alpr==0.3']

_LOGGER = logging.getLogger(__name__)

SERVICE_SCAN = 'scan'
SERVICE_RESTART = 'restart'

EVENT_FOUND = 'openalpr.found'

ATTR_PLATE = 'plate'


ENGINE_LOCAL = 'local'
ENGINE_CLOUD = 'cloud'

RENDER_IMAGE = 'image'
RENDER_FFMPEG = 'ffmpeg'

OPENALPR_REGIONS = [
    'us',
    'eu',
    'au',
    'auwide',
    'gb',
    'kr',
    'mx',
    'sg',
]

CONF_RENDER = 'render'
CONF_ENGINE = 'engine'
CONF_REGION = 'region'
CONF_INTERVAL = 'interval'
CONF_ENTITIES = 'entities'
CONF_CONFIDENCE = 'confidence'
CONF_ALPR_BINARY = 'alpr_binary'

DEFAULT_NAME = 'OpenAlpr'
DEFAULT_ENGINE = ENGINE_LOCAL
DEFAULT_RENDER = RENDER_FFMPEG
DEFAULT_BINARY = 'alpr'
DEFAULT_INTERVAL = 10
DEFAULT_CONFIDENCE = 80.0

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_RENDER, default=DEFAULT_RENDER):
        vol.In([RENDER_IMAGE, RENDER_FFMPEG]),
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ENGINE): vol.In([ENGINE_LOCAL, ENGINE_CLOUD]),
        vol.Required(CONF_REGION): vol.In(OPENALPR_REGIONS),
        vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE):
            vol.Coerce(float),
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ALPR_BINARY, default=DEFAULT_BINARY): cv.string,
        vol.Required(CONF_ENTITIES):
            vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
    })
}, extra=vol.ALLOW_EXTRA)


SERVICE_RESTART_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCAN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def scan(hass, entity_id=None):
    """Scan a image immediately."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_SCAN, data)


def restart(hass, entity_id=None):
    """Restart a ffmpeg process."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_RESTART, data)


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the OpenAlpr component."""
    engine = config[DOMAIN].get(CONF_ENGINE)
    region = config[DOMAIN].get(CONF_REGION)
    confidence = config[DOMAIN].get(CONF_CONFIDENCE)
    api_key = config[DOMAIN].get(CONF_API_KEY)
    binary = config[DOMAIN].get(CONF_ALPR_BINARY)
    use_render_fffmpeg = False

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    openalpr_device = []

    for device in config[DOMAIN].get(CONF_ENTITIES):
        input_source = device.get(CONF_INPUT)
        render = device.get(CONF_RENDER)

        ##
        # create api
        if engine == ENGINE_LOCAL:
            alpr_api = OpenalprApiLocal(
                confidence=confidence,
                region=region,
                binary=binary,
            )
        else:
            alpr_api = OpenalprApiCloud(
                confidence=confidence,
                region=region,
                api_key=api_key,
            )

        ##
        # Create Alpr device / render engine
        if render == RENDER_FFMPEG:
            use_render_fffmpeg = True
            if not run_test(input_source):
                _LOGGER.error("'%s' is not valid ffmpeg input", input_source)
                continue

            alpr_dev = OpenalprDeviceFFmpeg(
                name=device.get(CONF_NAME),
                interval=device.get(CONF_INTERVAL),
                api=alpr_api,
                input_source=input_source,
                extra_arguments=device.get(CONF_EXTRA_ARGUMENTS),
            )
        else:
            alpr_dev = OpenalprDeviceImage(
                name=device.get(CONF_NAME),
                interval=device.get(CONF_INTERVAL),
                api=alpr_api,
                input_source=input_source,
                username=device.get(CONF_USERNAME),
                password=device.get(CONF_PASSWORD),
            )

        # register shutdown event
        openalpr_device.append(alpr_dev)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, alpr_dev.shutdown)

    component.add_entities(openalpr_device)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def _handle_service_scan(service):
        """Handle service for immediately scan."""
        device_list = component.extract_from_service(service)

        for device in device_list:
            device.scan()

    hass.services.register(DOMAIN, SERVICE_SCAN,
                           _handle_service_scan,
                           descriptions[DOMAIN][SERVICE_SCAN],
                           schema=SERVICE_SCAN_SCHEMA)

    # Add restart service only if a device use ffmpeg as render
    if not use_render_fffmpeg:
        return True

    def _handle_service_restart(service):
        """Handle service for restart ffmpeg process."""
        device_list = component.extract_from_service(service)

        for device in device_list:
            device.restart()

    hass.services.register(DOMAIN, SERVICE_RESTART,
                           _handle_service_restart,
                           descriptions[DOMAIN][SERVICE_RESTART],
                           schema=SERVICE_RESTART_SCHEMA)

    return True


class OpenalprDevice(Entity):
    """Represent a openalpr device object for processing stream/images."""

    def __init__(self, name, interval, api):
        """Init image processing."""
        self._name = name
        self._interval = interval
        self._api = api
        self._last = {}

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        plate = STATE_UNKNOWN

        # search high plate
        for i_pl, i_co in self._last.items():
            if i_co > confidence:
                confidence = i_co
                plate = i_pl
        return plate

    def shutdown(self, event):
        """Close stream."""
        if hasattr(self._api, "shutdown"):
            self._api.shutdown(event)

    def restart(self):
        """Restart stream."""
        raise NotImplementedError()

    def _process_image(self, image):
        """Callback for processing image."""
        self._api.process_image(image, self._process_event)

    def _process_event(self, plates):
        """Send event with new plates."""
        state_change = False
        plates_set = set(plates)
        last_set = set(self._last)
        new_plates = plates_set - last_set

        # send events
        for i_plate in new_plates:
            self.hass.bus.fire(EVENT_FOUND, {
                ATTR_PLATE: i_plate,
                ATTR_ENTITY_ID: self.entity_id
            })

        # update entity store
        if last_set <= plates_set:
            state_change = True
        self._last = plates

        # update HA state
        if state_change:
            self.update_ha_state()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {'plates': self._last}

    def scan(self):
        """Immediately scan a image."""
        raise NotImplementedError()

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name


class OpenalprDeviceFFmpeg(OpenalprDevice):
    """Represent a openalpr device object for processing stream/images."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, interval, api, input_source,
                 extra_arguments=None):
        """Init image processing."""
        from haffmpeg import ImageStream, ImageSingle

        super().__init__(name, interval, api)
        self._input_source = input_source
        self._extra_arguments = extra_arguments

        if self._interval > 0:
            self._ffmpeg = ImageStream(get_binary(), self._process_image)
        else:
            self._ffmpeg = ImageSingle(get_binary())

        self._start_ffmpeg()

    def shutdown(self, event):
        """Close ffmpeg stream."""
        if self._interval > 0:
            self._ffmpeg.close()

    def restart(self):
        """Restart ffmpeg stream."""
        if self._interval > 0:
            self._ffmpeg.close()
            self._start_ffmpeg()

    def scan(self):
        """Immediately scan a image."""
        from haffmpeg import IMAGE_PNG

        # process single image
        if self._interval == 0:
            image = self._ffmpeg.get_image(
                self._input_source,
                output_format=IMAGE_PNG,
                extra_cmd=self._extra_arguments
            )
            return self._process_image(image)

        # stream
        self._ffmpeg.push_image()

    def _start_ffmpeg(self):
        """Start a ffmpeg image stream."""
        from haffmpeg import IMAGE_PNG
        if self._interval == 0:
            return

        self._ffmpeg.open_stream(
            input_source=self._input_source,
            interval=self._interval,
            output_format=IMAGE_PNG,
            extra_cmd=self._extra_arguments,
        )

    @property
    def should_poll(self):
        """Return True if render is be 'image' or False if 'ffmpeg'."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self._interval == 0 or self._ffmpeg.is_running


class OpenalprDeviceImage(OpenalprDevice):
    """Represent a openalpr device object for processing stream/images."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, interval, api, input_source,
                 username=None, password=None):
        """Init image processing."""
        super().__init__(name, interval, api)

        self._next = time()
        self._username = username
        self._password = password
        self._url = input_source

    def restart(self):
        """Fake restart with scan a picture."""
        self.scan()

    def scan(self):
        """Immediately scan a image."""
        # send request
        if self._username is not None and self._password is not None:
            req = requests.get(
                self._url, auth=(self._username, self._password), timeout=15)
        else:
            req = requests.get(self._url, timeout=15)

        # process image
        image = req.content
        self._process_image(image)

    @property
    def should_poll(self):
        """Return True if render is be 'image' or False if 'ffmpeg'."""
        return self._interval > 0

    def update(self):
        """Retrieve latest state."""
        if self._next > time():
            return
        self.scan()
        self._next = time() + self._interval


# pylint: disable=too-few-public-methods
class OpenalprApi(object):
    """OpenAlpr api class."""

    def __init__(self, region, confidence):
        """Init basic api processing."""
        self._region = region
        self._confidence = confidence

    def process_image(self, image, event_callback):
        """Callback for processing image."""
        raise NotImplementedError()


# pylint: disable=too-few-public-methods
class OpenalprApiCloud(OpenalprApi):
    """Use the cloud openalpr api to parse licences plate."""

    def __init__(self, region, confidence, api_key):
        """Init cloud api processing."""
        import openalpr_api

        super().__init__(region=region, confidence=confidence)
        self._api = openalpr_api.DefaultApi()
        self._api_key = api_key

    def process_image(self, image, event_callback):
        """Callback for processing image."""
        result = self._api.recognize_post(
            self._api_key,
            'plate',
            image="",
            image_bytes=str(b64encode(image), 'utf-8'),
            country=self._region
        )

        # process result
        f_plates = {}
        # pylint: disable=no-member
        for object_plate in result.plate.results:
            plate = object_plate.plate
            confidence = object_plate.confidence
            if confidence >= self._confidence:
                f_plates[plate] = confidence
        event_callback(f_plates)


class OpenalprApiLocal(OpenalprApi):
    """Use local openalpr library to parse licences plate."""

    def __init__(self, region, confidence, binary):
        """Init local api processing."""
        # pylint: disable=import-error
        from haalpr import HAAlpr

        super().__init__(region=region, confidence=confidence)
        self._api = HAAlpr(binary=binary, country=region)

    def process_image(self, image, event_callback):
        """Callback for processing image."""
        result = self._api.recognize_byte(image)

        # process result
        f_plates = {}
        for found in result:
            for plate, confidence in found.items():
                if confidence >= self._confidence:
                    f_plates[plate] = confidence
        event_callback(f_plates)
