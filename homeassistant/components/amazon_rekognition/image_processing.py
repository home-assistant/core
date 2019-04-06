"""
Platform that will perform object detection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing/amazon_rekognition
"""
import base64
import json
import logging
import time

import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)


_LOGGER = logging.getLogger(__name__)

CONF_REGION = 'region_name'
CONF_ACCESS_KEY_ID = 'aws_access_key_id'
CONF_SECRET_ACCESS_KEY = 'aws_secret_access_key'
CONF_TARGET = 'target'
DEFAULT_TARGET = 'Person'

DEFAULT_REGION = 'us-east-1'
SUPPORTED_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                     'ca-central-1', 'eu-west-1', 'eu-central-1', 'eu-west-2',
                     'eu-west-3', 'ap-southeast-1', 'ap-southeast-2',
                     'ap-northeast-2', 'ap-northeast-1', 'ap-south-1',
                     'sa-east-1']

REQUIREMENTS = ['boto3 == 1.9.69']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_REGION, default=DEFAULT_REGION):
        vol.In(SUPPORTED_REGIONS),
    vol.Required(CONF_ACCESS_KEY_ID): cv.string,
    vol.Required(CONF_SECRET_ACCESS_KEY): cv.string,
    vol.Optional(CONF_TARGET, default=DEFAULT_TARGET): cv.string,
})


def get_label_instances(response, target):
    """Get the number of instances of a target label."""
    for label in response['Labels']:
        if label['Name'] == target:
            return len(label['Instances'])
    return 0

def parse_labels(response):
    """Parse the API labels data, returning objects only."""
    return {label['Name']: round(label['Confidence'], 2) for label in response['Labels']}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Rekognition."""

    import boto3
    aws_config = {
        CONF_REGION: config.get(CONF_REGION),
        CONF_ACCESS_KEY_ID: config.get(CONF_ACCESS_KEY_ID),
        CONF_SECRET_ACCESS_KEY: config.get(CONF_SECRET_ACCESS_KEY),
        }

    client = boto3.client('rekognition', **aws_config) # Will not raise error.

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(Rekognition(
            client,
            config.get(CONF_REGION),
            config.get(CONF_TARGET),
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME),
        ))
    add_devices(entities)


class Rekognition(ImageProcessingEntity):
    """Perform object and label recognition."""

    def __init__(self, client, region, target, camera_entity, name=None):
        """Init with the client."""
        self._client = client
        self._region = region
        self._target = target
        if name:  # Since name is optional.
            self._name = name
        else:
            entity_name = split_entity_id(camera_entity)[1]
            self._name = "{} {} {}".format('rekognition', target, entity_name)
        self._camera_entity = camera_entity
        self._state = None  # The number of instances of interest
        self._labels = {} # The parsed label data

    def process_image(self, image):
        """Process an image."""
        self._state = None
        self._labels = {}
        response = self._client.detect_labels(Image={'Bytes': image})
        self._state = get_label_instances(response, self._target)
        self._labels = parse_labels(response)

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera_entity

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = self._labels
        attr['target'] = self._target
        return attr

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
