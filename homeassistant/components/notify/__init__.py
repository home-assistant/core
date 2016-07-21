"""
Provides functionality to notify people.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/notify/
"""
import io
import os
import logging

import voluptuous as vol
import requests

from homeassistant.config import load_yaml_config_file
from homeassistant.loader import get_component
from homeassistant.helpers import template
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_ENTITY_ID,
                                 STATE_UNKNOWN)

DOMAIN = 'notify'

# Title of notification
ATTR_TITLE = 'title'
ATTR_TITLE_DEFAULT = "Home Assistant"

# Target of the notification (user, device, etc)
ATTR_TARGET = 'target'

# Text to notify user of
ATTR_MESSAGE = 'message'

# Platform specific data
ATTR_FORMATS = 'formats'

ATTR_PHOTO = 'photo'

# others
ATTR_FILE = 'file'
ATTR_URL = 'url'
ATTR_CAPTION = 'caption'
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'

# HASS Device objects
ATTR_CAMERA = 'camera_entity'
ATTR_DEVICE = 'device_entity'

SERVICE_SEND_MESSAGE = 'send_message'
SERVICE_SEND_PHOTO = 'send_photo'
SERVICE_SEND_LOCATION = 'send_location'

MESSAGE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.template,
    vol.Optional(ATTR_TARGET): cv.string,
    vol.Optional(ATTR_FORMATS, default={}): dict,
})

PHOTO_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_URL): cv.string,
    vol.Optional(ATTR_FILE): cv.string,
    vol.Optional(ATTR_CAMERA): cv.template,
    vol.Optional(ATTR_CAPTION): cv.string,
    vol.Optional(ATTR_USERNAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
})

LOCATION_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_LATITUDE): cv.latitude,
    vol.Optional(ATTR_LONGITUDE): cv.longitude,
    vol.Optional(ATTR_DEVICE): cv.string,
    vol.Optional(ATTR_CAPTION): cv.template,
})


_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-arguments
def send_message(hass, message=None, entity_id=None, title=None, target=None,
                 formats=None):
    """Send a notification message."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TITLE, title),
            (ATTR_MESSAGE, message),
            (ATTR_TARGET, target),
            (ATTR_FORMATS, formats)
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SEND_MESSAGE, data)


# pylint: disable=too-many-arguments
def send_photo(hass, entity_id=None, url=None, file=None, camera_entity=None,
               caption=None, username=None, password=None):
    """Send a photo."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_URL, url),
            (ATTR_FILE, file),
            (ATTR_CAMERA, camera_entity),
            (ATTR_CAPTION, caption),
            (ATTR_USERNAME, username),
            (ATTR_PASSWORD, password)
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SEND_PHOTO, data)


# pylint: disable=too-many-arguments
def send_location(hass, entity_id=None, latitude=None, longitude=None,
                  device_entity=None, caption=None):
    """Send a location."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_LATITUDE, latitude),
            (ATTR_LONGITUDE, longitude),
            (ATTR_DEVICE, device_entity),
            (ATTR_CAPTION, caption)
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SEND_LOCATION, data)


def setup(hass, config):
    """Setup the notify services."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass)

    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def message_handle_service(service):
        """Handle sending notification message service calls."""
        message = service.data.get(ATTR_MESSAGE)

        title = template.render(
            hass, service.data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT))
        target = service.data.get(ATTR_TARGET)
        message = template.render(hass, message)
        formats = service.data.get(ATTR_FORMATS)

        for notify in component.extract_from_service(service):
            notify.send_message(message, title=title, target=target,
                                formats=formats)

    hass.services.register(DOMAIN, SERVICE_SEND_MESSAGE,
                           message_handle_service,
                           descriptions.get(SERVICE_SEND_MESSAGE),
                           schema=MESSAGE_SERVICE_SCHEMA)

    def photo_handle_service(service):
        """Handle sending photo service calls."""
        caption = service.data.get(ATTR_CAPTION, None)
        if caption is not None:
            caption = template.render(hass, caption)

        photo = service.data.copy()
        photo.pop(ATTR_CAPTION, None)
        photo.pop(ATTR_ENTITY_ID, None)

        for notify in component.extract_from_service(service):
            notify.send_photo(photo, caption=caption)

    hass.services.register(DOMAIN, SERVICE_SEND_PHOTO, photo_handle_service,
                           descriptions.get(SERVICE_SEND_PHOTO),
                           schema=PHOTO_SERVICE_SCHEMA)

    def location_handle_service(service):
        """Handle sending location service calls."""
        caption = service.data.get(ATTR_CAPTION, None)
        if caption is not None:
            caption = template.render(hass, caption)

        # load gps coordinate from device tracker or params
        device_id = service.data.get(ATTR_DEVICE, None)
        if device_id is not None:
            tracker = get_component(device_id)
            if not tracker.gps:
                _LOGGER.error("No gps data on device.")
                return

            latitude = float(tracker.gps[0])
            longitude = float(tracker.gps[1])
        else:
            latitude = service.data.get(ATTR_LATITUDE)
            longitude = service.data.get(ATTR_LONGITUDE)

        for notify in component.extract_from_service(service):
            notify.send_location(latitude, longitude, caption=caption)

    hass.services.register(DOMAIN, SERVICE_SEND_LOCATION,
                           location_handle_service,
                           descriptions.get(SERVICE_SEND_LOCATION),
                           schema=LOCATION_SERVICE_SCHEMA)

    return True


# pylint: disable=too-few-public-methods
class BaseNotificationService(Entity):
    """An abstract class for notification services."""

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain:
         - ATTR_TITLE to specify a title
         - ATTR_TARGET to specify a platform target
         - ATTR_FORMAT to specify a message format
        """
        raise NotImplementedError

    def send_photo(self, photo, **kwargs):
        """Send a photo.

        kwargs can contain:
         - ATTR_CAPTION to specify a cation
        """
        raise NotImplementedError

    def send_location(self, latitude, longitude, **kwargs):
        """Send a location.

        kwargs can contain:
         - ATTR_CAPTION to specify a cation
        """
        raise NotImplementedError

    @property
    def state(self):
        """Return the state property really does nothing for a notification."""
        return STATE_UNKNOWN

    @property
    def hidden(self):
        """Return True if the entity should be hidden from UIs."""
        return True

    @staticmethod
    def load_photo(url=None, file=None, camera_entity=None, username=None,
                   password=None):
        """Load photo into ByteIO/File container from a source."""
        try:
            if camera_entity is not None:
                # load photo from camera entity
                cam = get_component(camera_entity)
                if cam is None:
                    _LOGGER.error("Campera entity not found!")
                    return
                return io.BytesIO(cam.camera_image())

            elif url is not None:
                # load photo from url
                if username is not None and password is not None:
                    req = requests.get(url, auth=(username, password))
                else:
                    req = requests.get(url)
                return io.BytesIO(req.content)

            elif file is not None:
                # load photo from file
                return open(file, "rb")
            else:
                _LOGGER.warning("Can't load photo no photo found in params!")

        except (OSError, IOError, requests.exceptions.RequestException):
            _LOGGER.error("Can't load photo into ByteIO")

        return None
