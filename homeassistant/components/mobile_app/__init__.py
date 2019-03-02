"""Support for native mobile apps."""
import logging
import json
from functools import partial

import voluptuous as vol
from aiohttp.web import json_response, Response
from aiohttp.web_exceptions import HTTPBadRequest

from homeassistant import config_entries
from homeassistant.auth.util import generate_secret
import homeassistant.core as ha
from homeassistant.core import Context
from homeassistant.components import webhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN, SERVICE_SEE as DEVICE_TRACKER_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA as SEE_SCHEMA)
from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 HTTP_BAD_REQUEST, HTTP_CREATED,
                                 HTTP_INTERNAL_SERVER_ERROR, CONF_WEBHOOK_ID)
from homeassistant.exceptions import (HomeAssistantError, ServiceNotFound,
                                      TemplateError)
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.typing import HomeAssistantType

REQUIREMENTS = ['PyNaCl==1.3.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mobile_app'

DEPENDENCIES = ['device_tracker', 'http', 'webhook']

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_SECRET = 'secret'
CONF_USER_ID = 'user_id'

ATTR_APP_DATA = 'app_data'
ATTR_APP_ID = 'app_id'
ATTR_APP_NAME = 'app_name'
ATTR_APP_VERSION = 'app_version'
ATTR_DEVICE_NAME = 'device_name'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_MODEL = 'model'
ATTR_OS_VERSION = 'os_version'
ATTR_SUPPORTS_ENCRYPTION = 'supports_encryption'

ATTR_EVENT_DATA = 'event_data'
ATTR_EVENT_TYPE = 'event_type'

ATTR_TEMPLATE = 'template'
ATTR_TEMPLATE_VARIABLES = 'variables'

ATTR_WEBHOOK_DATA = 'data'
ATTR_WEBHOOK_ENCRYPTED = 'encrypted'
ATTR_WEBHOOK_ENCRYPTED_DATA = 'encrypted_data'
ATTR_WEBHOOK_TYPE = 'type'

WEBHOOK_TYPE_CALL_SERVICE = 'call_service'
WEBHOOK_TYPE_FIRE_EVENT = 'fire_event'
WEBHOOK_TYPE_RENDER_TEMPLATE = 'render_template'
WEBHOOK_TYPE_UPDATE_LOCATION = 'update_location'
WEBHOOK_TYPE_UPDATE_REGISTRATION = 'update_registration'

WEBHOOK_TYPES = [WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                 WEBHOOK_TYPE_RENDER_TEMPLATE, WEBHOOK_TYPE_UPDATE_LOCATION,
                 WEBHOOK_TYPE_UPDATE_REGISTRATION]

REGISTER_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_ID): cv.string,
    vol.Optional(ATTR_APP_NAME): cv.string,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
    vol.Required(ATTR_SUPPORTS_ENCRYPTION, default=False): cv.boolean,
})

UPDATE_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
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
    WEBHOOK_TYPE_UPDATE_REGISTRATION: UPDATE_DEVICE_SCHEMA,
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


def context(device):
    """Generate a context from a request."""
    return Context(user_id=device[CONF_USER_ID])


async def handle_webhook(store, hass: HomeAssistantType, webhook_id: str,
                         request):
    """Handle webhook callback."""
    device = hass.data[DOMAIN][webhook_id]

    try:
        req_data = await request.json()
    except ValueError:
        _LOGGER.warning('Received invalid JSON from mobile_app')
        return json_response([], status=HTTP_BAD_REQUEST)

    try:
        req_data = WEBHOOK_PAYLOAD_SCHEMA(req_data)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(req_data, ex)
        _LOGGER.error('Received invalid webhook payload: %s', err)
        return Response(status=200)

    webhook_type = req_data[ATTR_WEBHOOK_TYPE]

    webhook_payload = req_data.get(ATTR_WEBHOOK_DATA, {})

    if req_data[ATTR_WEBHOOK_ENCRYPTED]:
        enc_data = req_data[ATTR_WEBHOOK_ENCRYPTED_DATA]
        webhook_payload = _decrypt_payload(device[CONF_SECRET], enc_data)

    try:
        data = WEBHOOK_SCHEMAS[webhook_type](webhook_payload)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(webhook_payload, ex)
        _LOGGER.error('Received invalid webhook payload: %s', err)
        return Response(status=200)

    if webhook_type == WEBHOOK_TYPE_CALL_SERVICE:
        try:
            await hass.services.async_call(data[ATTR_DOMAIN],
                                           data[ATTR_SERVICE],
                                           data[ATTR_SERVICE_DATA],
                                           blocking=True,
                                           context=context(device))
        except (vol.Invalid, ServiceNotFound):
            raise HTTPBadRequest()

        return Response(status=200)

    if webhook_type == WEBHOOK_TYPE_FIRE_EVENT:
        event_type = data[ATTR_EVENT_TYPE]
        hass.bus.async_fire(event_type, data[ATTR_EVENT_DATA],
                            ha.EventOrigin.remote, context=context(device))
        return Response(status=200)

    if webhook_type == WEBHOOK_TYPE_RENDER_TEMPLATE:
        try:
            tpl = template.Template(data[ATTR_TEMPLATE], hass)
            rendered = tpl.async_render(data.get(ATTR_TEMPLATE_VARIABLES))
            return json_response({"rendered": rendered})
        except (ValueError, TemplateError) as ex:
            return json_response(({"error": ex}), status=HTTP_BAD_REQUEST)

    if webhook_type == WEBHOOK_TYPE_UPDATE_LOCATION:
        await hass.services.async_call(DEVICE_TRACKER_DOMAIN,
                                       DEVICE_TRACKER_SEE, data,
                                       blocking=True, context=context(device))
        return Response(status=200)

    if webhook_type == WEBHOOK_TYPE_UPDATE_REGISTRATION:
        data[ATTR_APP_ID] = device[ATTR_APP_ID]
        data[ATTR_APP_NAME] = device[ATTR_APP_NAME]
        data[ATTR_SUPPORTS_ENCRYPTION] = device[ATTR_SUPPORTS_ENCRYPTION]
        data[CONF_SECRET] = device[CONF_SECRET]
        data[CONF_USER_ID] = device[CONF_USER_ID]
        data[CONF_WEBHOOK_ID] = device[CONF_WEBHOOK_ID]

        hass.data[DOMAIN][webhook_id] = data

        try:
            await store.async_save(hass.data[DOMAIN])
        except HomeAssistantError as ex:
            _LOGGER.error("Error updating mobile_app registration: %s", ex)
            return Response(status=200)

        return json_response(safe_device(data))


def supports_encryption():
    """Test if we support encryption."""
    try:
        import nacl   # noqa pylint: disable=unused-import
        return True
    except OSError:
        return False


def safe_device(device: dict):
    """Return a device without webhook_id or secret."""
    return {
        ATTR_APP_DATA: device[ATTR_APP_DATA],
        ATTR_APP_ID: device[ATTR_APP_ID],
        ATTR_APP_NAME: device[ATTR_APP_NAME],
        ATTR_APP_VERSION: device[ATTR_APP_VERSION],
        ATTR_DEVICE_NAME: device[ATTR_DEVICE_NAME],
        ATTR_MANUFACTURER: device[ATTR_MANUFACTURER],
        ATTR_MODEL: device[ATTR_MODEL],
        ATTR_OS_VERSION: device[ATTR_OS_VERSION],
        ATTR_SUPPORTS_ENCRYPTION: device[ATTR_SUPPORTS_ENCRYPTION],
    }


def register_device_webhook(hass: HomeAssistantType, store, device):
    """Register the webhook for a device."""
    device_name = 'Mobile App: {}'.format(device[ATTR_DEVICE_NAME])
    webhook_id = device[CONF_WEBHOOK_ID]
    webhook.async_register(hass, DOMAIN, device_name, webhook_id,
                           partial(handle_webhook, store))


async def async_setup(hass, config):
    """Set up the mobile app component."""
    conf = config.get(DOMAIN)

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {}

    hass.data[DOMAIN] = app_config

    for device in app_config.values():
        register_device_webhook(hass, store, device)

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    hass.http.register_view(DevicesView(store))

    return True


async def async_setup_entry(hass, entry):
    """Set up an mobile_app entry."""
    return True


class DevicesView(HomeAssistantView):
    """A view that accepts device registration requests."""

    url = '/api/mobile_app/devices'
    name = 'api:mobile_app:register-device'

    def __init__(self, store):
        """Initialize the view."""
        self._store = store

    @RequestDataValidator(REGISTER_DEVICE_SCHEMA)
    async def post(self, request, data):
        """Handle the POST request for device registration."""
        hass = request.app['hass']

        resp = {}

        webhook_id = generate_secret()

        data[CONF_WEBHOOK_ID] = resp[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] and supports_encryption():
            secret = generate_secret(16)

            data[CONF_SECRET] = resp[CONF_SECRET] = secret

        data[CONF_USER_ID] = request['hass_user'].id

        hass.data[DOMAIN][webhook_id] = data

        try:
            await self._store.async_save(hass.data[DOMAIN])
        except HomeAssistantError:
            return self.json_message("Error saving device.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        register_device_webhook(hass, self._store, data)

        return self.json(resp, status_code=HTTP_CREATED)
