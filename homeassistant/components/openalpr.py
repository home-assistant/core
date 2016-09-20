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
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.ffmpeg import (
    get_binary, run_test, CONF_INPUT, CONF_EXTRA_ARGUMENTS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'openalpr'
DEPENDENCIES = ['ffmpeg']
REQUIREMENTS = [
    'git+https://github.com/pvizeli/cloudapi.git'
    '#egg=openalpr_api&subdirectory=python']

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
CONF_RUNTIME = 'runtime'
CONF_INTERVAL = 'interval'
CONF_ENTITIES = 'entities'

DEFAULT_NAME = 'OpenAlpr'
DEFAULT_ENGINE = ENGINE_LOCAL
DEFAULT_RENDER = RENDER_FFMPEG
DEFAULT_INTERVAL = 2

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
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_RUNTIME): vol.IsDir,
        vol.Required(CONF_ENTITIES): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
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


def setup(hass, config):
    """Setup the OpenAlpr component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    openalpr_device = []

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    engine = config[DOMAIN].get(CONF_ENGINE)
    region = config[DOMAIN].get(CONF_REGION)
    api_key = config[DOMAIN].get(CONF_API_KEY)
    runtime = config[DOMAIN].get(CONF_RUNTIME)
    use_render_fffmpeg = False
    for device in config[DOMAIN].get(CONF_ENTITIES):
        input_source = device.get(CONF_INPUT)
        render = device.get(CONF_RENDER)

        # if render ffmpeg, test input
        if render == RENDER_FFMPEG:
            use_render_fffmpeg = True
            if not run_test(input_source):
                _LOGGER.error("'%s' is not valid ffmpeg input", input_source)
                continue

        # if local openalpr engine, check if exists
        if engine == ENGINE_LOCAL:
            try:
                # pylint: disable=unused-variable
                from openalpr import Alpr  # NOQA
            except ImportError:
                _LOGGER.error("Local openalpr instalation not exists")
                continue

            alpr_dev = OpenalprDeviceLocal(
                name=device.get(CONF_NAME),
                render=render,
                interval=device.get(CONF_INTERVAL),
                input_source=input_source,
                runtime=runtime,
                region=region,
                extra_arguments=device.get(CONF_EXTRA_ARGUMENTS),
                username=device.get(CONF_USERNAME),
                password=device.get(CONF_PASSWORD),
            )

        else:
            alpr_dev = OpenalprDeviceCloud(
                name=device.get(CONF_NAME),
                render=render,
                interval=device.get(CONF_INTERVAL),
                input_source=input_source,
                api_key=api_key,
                region=region,
                extra_arguments=device.get(CONF_EXTRA_ARGUMENTS),
                username=device.get(CONF_USERNAME),
                password=device.get(CONF_PASSWORD),
            )

        # register shutdown event
        openalpr_device.append(alpr_dev)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, alpr_dev.shutdown)

    component.add_entities(openalpr_device)

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


# pylint: disable=too-many-instance-attributes
class OpenalprDevice(Entity):
    """Represent a openalpr device object for processing stream/images."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, render, interval, input_source,
                 extra_arguments=None, username=None, password=None):
        """Init image processing."""
        from haffmpeg import ImageStream

        self._name = name
        self._render = render
        self._interval = interval
        self._last = set()

        # generade input source
        if self._render == RENDER_FFMPEG:
            self._ffmpeg = ImageStream(get_binary(), self._process_image)
            self._input_source = input_source
            self._extra_arguments = extra_arguments
            self._start_ffmpeg()
        else:
            self._ffmpeg = None
            self._next = time()
            self._username = username
            self._password = password
            self._url = input_source

    def shutdown(self, event):
        """Close ffmpeg stream."""
        if self._render == RENDER_FFMPEG:
            self._ffmpeg.close()

    def restart(self):
        """Restart ffmpeg stream."""
        if self._render == RENDER_FFMPEG:
            self._ffmpeg.close()
            self._start_ffmpeg()

    def _process_image(self, image):
        """Callback for processing image."""
        raise NotImplementedError

    def _process_event(self, plates):
        """Send event with new plates."""
        new_plates = plates - self._last

        # send events
        for i_plate in new_plates:
            self.hass.buss.fire(EVENT_FOUND, {
                ATTR_PLATE: i_plate,
                ATTR_ENTITY_ID: self.entity_id
            })
        self._last = plates.copy()

    def scan(self):
        """Immediately scan a image."""
        if self._render == RENDER_FFMPEG:
            self._ffmpeg.push_image()
        else:
            self._next = time()
            self.update()

    def _start_ffmpeg(self):
        """Start a ffmpeg image stream."""
        from haffmpeg import IMAGE_PNG

        if self._render == RENDER_FFMPEG:
            self._ffmpeg.open_stream(
                input_source=self._input_source,
                interval=self._interval,
                output_format=IMAGE_PNG,
                extra_cmd=self._extra_arguments,
            )

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def hidden(self):
        """Return True if the entity should be hidden from UIs."""
        return True

    @property
    def should_poll(self):
        """Return True if render is be 'image' or False if 'ffmpeg'."""
        if self._render == RENDER_IMAGE:
            return True
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        if self._render == RENDER_IMAGE:
            return True

        # ffmpeg process
        return self._ffmpeg.is_running

    def update(self):
        """Retrieve latest state."""
        if self._render != RENDER_IMAGE or self._next > time():
            return

        # send request
        if self._username is not None and self._password is not None:
            req = requests.get(
                self._url, auth=(self._username, self._password), timeout=15)
        else:
            req = requests.get(self._url, timeout=15)

        # process image
        image = req.content
        self._next = time() + self._interval
        self._process_image(image)


class OpenalprDeviceCloud(OpenalprDevice):
    """Use local openalpr library to parse licences plate."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, render, interval, input_source, api_key, region,
                 extra_arguments=None, username=None, password=None):
        """Init image processing."""
        import openalpr_api

        self._api = openalpr_api.DefaultApi()
        self._api_key = api_key
        self._region = region

        # init render
        super().__init__(
            name=name, render=render, interval=interval,
            input_source=input_source, extra_arguments=extra_arguments,
            username=username, password=password)

    def _process_image(self, image):
        """Callback for processing image."""
        result = self._api.recognize_post(
            self._api_key,
            'plate',
            image="",
            image_bytes=b64encode(image),
            country=self._region
        )

        # process result
        f_plates = set()
        # pylint: disable=no-member
        for object_plate in result.plate.results:
            f_plates.add(object_plate.plate)
        self._process_event(f_plates)


class OpenalprDeviceLocal(OpenalprDevice):
    """Use the cloud openalpr api to parse licences plate."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, render, interval, input_source, runtime, region,
                 extra_arguments=None, username=None, password=None):
        """Init image processing."""
        # pylint: disable=import-error
        from openalpr import Alpr

        self._api = Alpr(region, "", runtime)

        # init render
        super().__init__(
            name=name, render=render, interval=interval,
            input_source=input_source, extra_arguments=extra_arguments,
            username=username, password=password)

    def shutdown(self, event):
        """Close api stuff."""
        super().shutdown(event)
        self._api.unload()

    def _process_image(self, image):
        """Callback for processing image."""
        result = self._api.recognize_array(image)

        # process result
        f_plates = set()
        for plate in result.get('results'):
            for candidate in plate.get('candidates'):
                f_plates.add(candidate.get('plate'))
                break
        self._process_event(f_plates)
