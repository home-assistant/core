"""Support for native mobile apps."""
import logging

import voluptuous as vol
from aiohttp.web import json_response

from homeassistant import config_entries
from homeassistant.auth.util import generate_secret
from homeassistant.components import webhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN, SERVICE_SEE as DEVICE_TRACKER_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA as SEE_SCHEMA)
from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR,
                                 CONF_WEBHOOK_ID)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers import template
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mobile_app'

DEPENDENCIES = ['device_tracker', 'http', 'webhook']

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_SECRET = 'secret'

ATTR_DEVICE_ID = 'device_id'

ATTR_DEVICE_NAME = 'device_name'

ATTR_APP_ID = 'app_id'
ATTR_APP_VERSION = 'app_version'

ATTR_EVENT_TYPE = 'event_type'
ATTR_EVENT_DATA = 'event_data'

ATTR_TEMPLATE = 'template'
ATTR_TEMPLATE_VARIABLES = 'variables'

REGISTER_DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_DEVICE_ID): cv.string,
    vol.Required(ATTR_APP_ID): cv.string,
    vol.Required(ATTR_APP_VERSION): cv.string,
}, extra=vol.ALLOW_EXTRA)

CALL_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DOMAIN): cv.string,
    vol.Required(ATTR_SERVICE): cv.string,
    vol.Optional(ATTR_SERVICE_DATA, default={}): dict,
})

FIRE_EVENT_SCHEMA = vol.Schema({
    vol.Required(ATTR_EVENT_TYPE): cv.string,
    vol.Optional(ATTR_EVENT_DATA, default={}): dict,
})

RENDER_TEMPLATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEMPLATE): cv.string,
    vol.Optional(ATTR_TEMPLATE_VARIABLES, default={}): dict,
})


async def handle_webhook(hass: HomeAssistantType, webhook_id: str, request):
    """Handle webhook callback."""
    req_data = await request.json()

    webhook_type = req_data.get('type')

    if webhook_type == 'call_service':
        try:
            data = CALL_SERVICE_SCHEMA(req_data)
        except vol.Invalid as ex:
            return json_response(vol.humanize.humanize_error(request.json, ex),
                                 HTTP_BAD_REQUEST)

        await hass.services.async_call(data[ATTR_DOMAIN], data[ATTR_SERVICE],
                                       data[ATTR_SERVICE_DATA])
    elif webhook_type == 'fire_event':
        try:
            data = FIRE_EVENT_SCHEMA(req_data)
        except vol.Invalid as ex:
            return json_response(vol.humanize.humanize_error(request.json, ex),
                                 HTTP_BAD_REQUEST)

        hass.bus.fire(data[ATTR_EVENT_TYPE], data[ATTR_EVENT_DATA])
    elif webhook_type == 'render_template':
        try:
            data = RENDER_TEMPLATE_SCHEMA(req_data)
        except vol.Invalid as ex:
            return json_response(vol.humanize.humanize_error(request.json, ex),
                                 HTTP_BAD_REQUEST)

        tpl = template.Template(data[ATTR_TEMPLATE], hass)
        return tpl.async_render(data.get(ATTR_TEMPLATE_VARIABLES))
    elif webhook_type == 'update_location':
        try:
            data = SEE_SCHEMA(req_data)
        except vol.Invalid as ex:
            return json_response(vol.humanize.humanize_error(request.json, ex),
                                 HTTP_BAD_REQUEST)

        await hass.services.async_call(DEVICE_TRACKER_DOMAIN,
                                       DEVICE_TRACKER_SEE, data)


def supports_encryption():
    """Test if we support encryption."""
    try:
        import libnacl   # noqa pylint: disable=unused-import
        return True
    except OSError:
        return False


async def async_setup(hass, config):
    """Set up the mobile app component."""
    conf = config.get(DOMAIN)

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {}

    hass.data[DOMAIN] = app_config

    for name, device in app_config.items():
        if CONF_WEBHOOK_ID in device:
            webhook.async_register(hass, DOMAIN, 'Mobile app',
                                   device[CONF_WEBHOOK_ID], handle_webhook)

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up an mobile app entry."""
    hass.http.register_view(RegisterDeviceView())

    return True


class RegisterDeviceView(HomeAssistantView):
    """A view that accepts device registration requests."""

    url = '/api/mobile_app/identify'
    name = 'api:mobile_app:identify'

    def __init__(self):
        """Initialize the view."""

    async def post(self, request):
        """Handle the POST request for device registration."""
        try:
            req_data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        hass = request.app['hass']

        try:
            data = REGISTER_DEVICE_SCHEMA(req_data)
        except vol.Invalid as ex:
            return self.json_message(
                vol.humanize.humanize_error(request.json, ex),
                HTTP_BAD_REQUEST)

        name = data.get(ATTR_DEVICE_ID)

        existing_device = hass.data[DOMAIN][name]

        webhook_id = existing_device.get(CONF_WEBHOOK_ID,
                                         generate_secret())

        secret = existing_device.get(CONF_SECRET, generate_secret(16))

        data[CONF_SECRET] = secret
        data[CONF_WEBHOOK_ID] = webhook_id

        hass.data[DOMAIN][name] = data

        store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

        try:
            await store.async_save(hass.data[DOMAIN])
        except HomeAssistantError:
            return self.json_message("Error saving device.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        if webhook_id not in hass.data.get('webhook', {}):
            webhook.async_register(hass, DOMAIN, 'Mobile app', webhook_id,
                                   handle_webhook)

        return self.json({'webhook_id': webhook_id, 'secret': secret})


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Mobile App', lambda *_: True,
    config_entries.CONN_CLASS_CLOUD_PUSH)
