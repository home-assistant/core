"""RESTful platform for notify component."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BAD_REQUEST,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_OK,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import setup_reload_service

from . import DOMAIN, PLATFORMS

CONF_DATA = "data"
CONF_DATA_TEMPLATE = "data_template"
CONF_MESSAGE_PARAMETER_NAME = "message_param_name"
CONF_TARGET_PARAMETER_NAME = "target_param_name"
CONF_TITLE_PARAMETER_NAME = "title_param_name"
DEFAULT_MESSAGE_PARAM_NAME = "message"
DEFAULT_METHOD = "GET"
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(
            CONF_MESSAGE_PARAMETER_NAME, default=DEFAULT_MESSAGE_PARAM_NAME
        ): cv.string,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(
            ["POST", "GET", "POST_JSON"]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TARGET_PARAMETER_NAME): cv.string,
        vol.Optional(CONF_TITLE_PARAMETER_NAME): cv.string,
        vol.Optional(CONF_DATA): dict,
        vol.Optional(CONF_DATA_TEMPLATE): {cv.match_all: cv.template_complex},
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the RESTful notification service."""
    setup_reload_service(hass, DOMAIN, PLATFORMS)

    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    headers = config.get(CONF_HEADERS)
    message_param_name = config.get(CONF_MESSAGE_PARAMETER_NAME)
    title_param_name = config.get(CONF_TITLE_PARAMETER_NAME)
    target_param_name = config.get(CONF_TARGET_PARAMETER_NAME)
    data = config.get(CONF_DATA)
    data_template = config.get(CONF_DATA_TEMPLATE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = requests.auth.HTTPDigestAuth(username, password)
        else:
            auth = requests.auth.HTTPBasicAuth(username, password)
    else:
        auth = None

    return RestNotificationService(
        hass,
        resource,
        method,
        headers,
        message_param_name,
        title_param_name,
        target_param_name,
        data,
        data_template,
        auth,
        verify_ssl,
    )


class RestNotificationService(BaseNotificationService):
    """Implementation of a notification service for REST."""

    def __init__(
        self,
        hass,
        resource,
        method,
        headers,
        message_param_name,
        title_param_name,
        target_param_name,
        data,
        data_template,
        auth,
        verify_ssl,
    ):
        """Initialize the service."""
        self._resource = resource
        self._hass = hass
        self._method = method.upper()
        self._headers = headers
        self._message_param_name = message_param_name
        self._title_param_name = title_param_name
        self._target_param_name = target_param_name
        self._data = data
        self._data_template = data_template
        self._auth = auth
        self._verify_ssl = verify_ssl

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {self._message_param_name: message}

        if self._title_param_name is not None:
            data[self._title_param_name] = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if self._target_param_name is not None and ATTR_TARGET in kwargs:
            # Target is a list as of 0.29 and we don't want to break existing
            # integrations, so just return the first target in the list.
            data[self._target_param_name] = kwargs[ATTR_TARGET][0]

        if self._data:
            data.update(self._data)
        elif self._data_template:
            kwargs[ATTR_MESSAGE] = message

            def _data_template_creator(value):
                """Recursive template creator helper function."""
                if isinstance(value, list):
                    return [_data_template_creator(item) for item in value]
                if isinstance(value, dict):
                    return {
                        key: _data_template_creator(item) for key, item in value.items()
                    }
                value.hass = self._hass
                return value.async_render(kwargs, parse_result=False)

            data.update(_data_template_creator(self._data_template))

        if self._method == "POST":
            response = requests.post(
                self._resource,
                headers=self._headers,
                data=data,
                timeout=10,
                auth=self._auth,
                verify=self._verify_ssl,
            )
        elif self._method == "POST_JSON":
            response = requests.post(
                self._resource,
                headers=self._headers,
                json=data,
                timeout=10,
                auth=self._auth,
                verify=self._verify_ssl,
            )
        else:  # default GET
            response = requests.get(
                self._resource,
                headers=self._headers,
                params=data,
                timeout=10,
                auth=self._auth,
                verify=self._verify_ssl,
            )

        if (
            response.status_code >= HTTP_INTERNAL_SERVER_ERROR
            and response.status_code < 600
        ):
            _LOGGER.exception(
                "Server error. Response %d: %s:", response.status_code, response.reason
            )
        elif (
            response.status_code >= HTTP_BAD_REQUEST
            and response.status_code < HTTP_INTERNAL_SERVER_ERROR
        ):
            _LOGGER.exception(
                "Client error. Response %d: %s:", response.status_code, response.reason
            )
        elif response.status_code >= HTTP_OK and response.status_code < 300:
            _LOGGER.debug(
                "Success. Response %d: %s:", response.status_code, response.reason
            )
        else:
            _LOGGER.debug("Response %d: %s:", response.status_code, response.reason)
