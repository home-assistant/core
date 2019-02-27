"""Support for native mobile apps."""
import logging
import json

import voluptuous as vol
from aiohttp.web import json_response
from aiohttp.web_exceptions import HTTPBadRequest

from homeassistant import config_entries
from homeassistant.auth.util import generate_secret
import homeassistant.core as ha
from homeassistant.core import Context
from homeassistant.components import webhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN, SERVICE_SEE as DEVICE_TRACKER_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA as SEE_SCHEMA)
from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR,
                                 CONF_WEBHOOK_ID)
from homeassistant.exceptions import (HomeAssistantError, ServiceNotFound,
                                      TemplateError)
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers import template
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.state import AsyncTrackStates

REQUIREMENTS = ['PyNaCl==1.3.0']

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
ATTR_SUPPORTS_ENCRYPTION = 'supports_encryption'

ATTR_EVENT_TYPE = 'event_type'
ATTR_EVENT_DATA = 'event_data'

ATTR_TEMPLATE = 'template'
ATTR_TEMPLATE_VARIABLES = 'variables'

ATTR_WEBHOOK_TYPE = 'type'
ATTR_WEBHOOK_DATA = 'data'
ATTR_WEBHOOK_ENCRYPTED = 'encrypted'
ATTR_WEBHOOK_ENCRYPTED_DATA = 'encrypted_data'

WEBHOOK_TYPE_CALL_SERVICE = 'call_service'
WEBHOOK_TYPE_FIRE_EVENT = 'fire_event'
WEBHOOK_TYPE_RENDER_TEMPLATE = 'render_template'
WEBHOOK_TYPE_UPDATE_LOCATION = 'update_location'

WEBHOOK_TYPES = [WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                 WEBHOOK_TYPE_RENDER_TEMPLATE, WEBHOOK_TYPE_UPDATE_LOCATION]

REGISTER_DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_DEVICE_ID): cv.string,
    vol.Required(ATTR_APP_ID): cv.string,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_SUPPORTS_ENCRYPTION, default=True): cv.boolean,
})

WEBHOOK_PAYLOAD_SCHEMA = vol.Schema({
    vol.Required(ATTR_WEBHOOK_TYPE): vol.In(WEBHOOK_TYPES),
    vol.Required(ATTR_WEBHOOK_DATA, default={}): dict,
    vol.Optional(ATTR_WEBHOOK_ENCRYPTED, default=False): cv.boolean,
    vol.Optional(ATTR_WEBHOOK_ENCRYPTED_DATA): cv.string,
})

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

WEBHOOK_SCHEMAS = {
    WEBHOOK_TYPE_CALL_SERVICE: CALL_SERVICE_SCHEMA,
    WEBHOOK_TYPE_FIRE_EVENT: FIRE_EVENT_SCHEMA,
    WEBHOOK_TYPE_RENDER_TEMPLATE: RENDER_TEMPLATE_SCHEMA,
    WEBHOOK_TYPE_UPDATE_LOCATION: SEE_SCHEMA,
}


def get_cipher():
    """Return decryption function and length of key.

    Async friendly.
    """
    from nacl.secret import SecretBox
    from nacl.encoding import Base64Encoder

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key).decrypt(ciphertext, encoder=Base64Encoder)
    return (SecretBox.KEY_SIZE, decrypt)


def _decrypt_payload(key, ciphertext):
    """Decrypt encrypted payload."""
    try:
        keylen, decrypt = get_cipher()
    except OSError:
        _LOGGER.warning(
            "Ignoring encrypted payload because libsodium not installed")
        return None

    if key is None:
        _LOGGER.warning(
            "Ignoring encrypted payload because no decryption key known")
        return None

    key = key.encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    try:
        message = decrypt(ciphertext, key)
        message = json.loads(message.decode("utf-8"))
        _LOGGER.debug("Successfully decrypted mobile_app payload")
        return message
    except ValueError:
        _LOGGER.warning("Ignoring encrypted payload because unable to decrypt")
        return None


def context(request):
    """Generate a context from a request."""
    user = request.get('hass_user')
    if user is None:
        return Context()

    return Context(user_id=user.id)


async def handle_webhook(hass: HomeAssistantType, webhook_id: str, request):
    """Handle webhook callback."""
    device = device_for_webhook_id(hass, webhook_id)

    req_data = await request.json()

    try:
        req_data = WEBHOOK_PAYLOAD_SCHEMA(req_data)
    except vol.Invalid as ex:
        return json_response(vol.humanize.humanize_error(req_data, ex),
                             status=HTTP_BAD_REQUEST)

    webhook_type = req_data[ATTR_WEBHOOK_TYPE]

    webhook_payload = req_data.get(ATTR_WEBHOOK_DATA, {})

    if req_data[ATTR_WEBHOOK_ENCRYPTED]:
        enc_data = req_data[ATTR_WEBHOOK_ENCRYPTED_DATA]
        webhook_payload = _decrypt_payload(device[CONF_SECRET], enc_data)

    try:
        data = WEBHOOK_SCHEMAS[webhook_type](webhook_payload)
    except vol.Invalid as ex:
        return json_response(vol.humanize.humanize_error(webhook_payload, ex),
                             status=HTTP_BAD_REQUEST)

    if webhook_type == WEBHOOK_TYPE_CALL_SERVICE:

        with AsyncTrackStates(hass) as changed_states:
            try:
                await hass.services.async_call(data[ATTR_DOMAIN],
                                               data[ATTR_SERVICE],
                                               data[ATTR_SERVICE_DATA],
                                               True,
                                               context(request))
            except (vol.Invalid, ServiceNotFound):
                raise HTTPBadRequest()

        return json_response(changed_states)
    elif webhook_type == WEBHOOK_TYPE_FIRE_EVENT:
        event_type = data[ATTR_EVENT_TYPE]
        hass.bus.fire(event_type, data[ATTR_EVENT_DATA], ha.EventOrigin.remote,
                      context(request))
        return json_response({"message": "Event {} fired.".format(event_type)})
    elif webhook_type == WEBHOOK_TYPE_RENDER_TEMPLATE:
        try:
            tpl = template.Template(data[ATTR_TEMPLATE], hass)
            rendered = tpl.async_render(data.get(ATTR_TEMPLATE_VARIABLES))
            return json_response({"rendered": rendered})
        except (ValueError, TemplateError) as ex:
            return json_response("Error rendering template: {}".format(ex),
                                 status=HTTP_BAD_REQUEST)

    elif webhook_type == WEBHOOK_TYPE_UPDATE_LOCATION:
        await hass.services.async_call(DEVICE_TRACKER_DOMAIN,
                                       DEVICE_TRACKER_SEE, data)
        return json_response([])


def supports_encryption():
    """Test if we support encryption."""
    try:
        import nacl   # noqa pylint: disable=unused-import
        return True
    except OSError:
        return False


def device_for_webhook_id(hass, webhook_id):
    """Return the device name for the webhook ID."""
    for device_name, device in hass.data[DOMAIN].items():
        if device.get(CONF_WEBHOOK_ID) == webhook_id:
            return device
    return None


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

    url = '/api/mobile_app/register'
    name = 'api:mobile_app:register'

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
                vol.humanize.humanize_error(req_data, ex),
                HTTP_BAD_REQUEST)

        device_id = data[ATTR_DEVICE_ID]

        if device_id in hass.data[DOMAIN]:
            return self.json(hass.data[DOMAIN][device_id])

        resp = {}

        webhook_id = generate_secret()

        data[CONF_WEBHOOK_ID] = webhook_id

        resp[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] is True and supports_encryption():
            secret = generate_secret(16)

            data[CONF_SECRET] = secret

            resp[CONF_SECRET] = secret

        hass.data[DOMAIN][device_id] = data

        store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

        try:
            await store.async_save(hass.data[DOMAIN])
        except HomeAssistantError:
            return self.json_message("Error saving device.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        if webhook_id not in hass.data.get('webhook', {}):
            webhook.async_register(hass, DOMAIN, 'Mobile app', webhook_id,
                                   handle_webhook)

        return self.json(resp)


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Mobile App', lambda *_: True,
    config_entries.CONN_CLASS_CLOUD_PUSH)
