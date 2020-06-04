"""Webhook handlers for mobile_app."""
from functools import wraps
import logging
import secrets

from aiohttp.web import HTTPBadRequest, Request, Response, json_response
from nacl.secret import SecretBox
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES as BINARY_SENSOR_CLASSES,
)
from homeassistant.components.device_tracker import (
    ATTR_BATTERY,
    ATTR_GPS,
    ATTR_GPS_ACCURACY,
    ATTR_LOCATION_NAME,
)
from homeassistant.components.frontend import MANIFEST_JSON
from homeassistant.components.sensor import DEVICE_CLASSES as SENSOR_CLASSES
from homeassistant.components.zone.const import DOMAIN as ZONE_DOMAIN
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    CONF_WEBHOOK_ID,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
)
from homeassistant.core import EventOrigin
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound, TemplateError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.template import attach
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.decorator import Registry

from .const import (
    ATTR_ALTITUDE,
    ATTR_APP_DATA,
    ATTR_APP_VERSION,
    ATTR_COURSE,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_EVENT_DATA,
    ATTR_EVENT_TYPE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_VERSION,
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_NAME,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_TYPE,
    ATTR_SENSOR_TYPE_BINARY_SENSOR,
    ATTR_SENSOR_TYPE_SENSOR,
    ATTR_SENSOR_UNIQUE_ID,
    ATTR_SENSOR_UOM,
    ATTR_SPEED,
    ATTR_SUPPORTS_ENCRYPTION,
    ATTR_TEMPLATE,
    ATTR_TEMPLATE_VARIABLES,
    ATTR_VERTICAL_ACCURACY,
    ATTR_WEBHOOK_DATA,
    ATTR_WEBHOOK_ENCRYPTED,
    ATTR_WEBHOOK_ENCRYPTED_DATA,
    ATTR_WEBHOOK_TYPE,
    CONF_CLOUDHOOK_URL,
    CONF_REMOTE_UI_URL,
    CONF_SECRET,
    DATA_CONFIG_ENTRIES,
    DATA_DELETED_IDS,
    DATA_STORE,
    DOMAIN,
    ERR_ENCRYPTION_ALREADY_ENABLED,
    ERR_ENCRYPTION_NOT_AVAILABLE,
    ERR_ENCRYPTION_REQUIRED,
    ERR_INVALID_FORMAT,
    ERR_SENSOR_DUPLICATE_UNIQUE_ID,
    ERR_SENSOR_NOT_REGISTERED,
    SIGNAL_LOCATION_UPDATE,
    SIGNAL_SENSOR_UPDATE,
)
from .helpers import (
    _decrypt_payload,
    empty_okay_response,
    error_response,
    registration_context,
    safe_registration,
    savable_state,
    supports_encryption,
    webhook_response,
)

_LOGGER = logging.getLogger(__name__)


WEBHOOK_COMMANDS = Registry()

COMBINED_CLASSES = set(BINARY_SENSOR_CLASSES + SENSOR_CLASSES)
SENSOR_TYPES = [ATTR_SENSOR_TYPE_BINARY_SENSOR, ATTR_SENSOR_TYPE_SENSOR]

WEBHOOK_PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_WEBHOOK_TYPE): cv.string,
        vol.Required(ATTR_WEBHOOK_DATA, default={}): vol.Any(dict, list),
        vol.Optional(ATTR_WEBHOOK_ENCRYPTED, default=False): cv.boolean,
        vol.Optional(ATTR_WEBHOOK_ENCRYPTED_DATA): cv.string,
    }
)


def validate_schema(schema):
    """Decorate a webhook function with a schema."""
    if isinstance(schema, dict):
        schema = vol.Schema(schema)

    def wrapper(func):
        """Wrap function so we validate schema."""

        @wraps(func)
        async def validate_and_run(hass, config_entry, data):
            """Validate input and call handler."""
            try:
                data = schema(data)
            except vol.Invalid as ex:
                err = vol.humanize.humanize_error(data, ex)
                _LOGGER.error("Received invalid webhook payload: %s", err)
                return empty_okay_response()

            return await func(hass, config_entry, data)

        return validate_and_run

    return wrapper


async def handle_webhook(
    hass: HomeAssistantType, webhook_id: str, request: Request
) -> Response:
    """Handle webhook callback."""
    if webhook_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        return Response(status=410)

    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]

    try:
        req_data = await request.json()
    except ValueError:
        _LOGGER.warning("Received invalid JSON from mobile_app")
        return empty_okay_response(status=HTTP_BAD_REQUEST)

    if (
        ATTR_WEBHOOK_ENCRYPTED not in req_data
        and config_entry.data[ATTR_SUPPORTS_ENCRYPTION]
    ):
        _LOGGER.warning(
            "Refusing to accept unencrypted webhook from %s",
            config_entry.data[ATTR_DEVICE_NAME],
        )
        return error_response(ERR_ENCRYPTION_REQUIRED, "Encryption required")

    try:
        req_data = WEBHOOK_PAYLOAD_SCHEMA(req_data)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(req_data, ex)
        _LOGGER.error("Received invalid webhook payload: %s", err)
        return empty_okay_response()

    webhook_type = req_data[ATTR_WEBHOOK_TYPE]

    webhook_payload = req_data.get(ATTR_WEBHOOK_DATA, {})

    if req_data[ATTR_WEBHOOK_ENCRYPTED]:
        enc_data = req_data[ATTR_WEBHOOK_ENCRYPTED_DATA]
        webhook_payload = _decrypt_payload(config_entry.data[CONF_SECRET], enc_data)

    if webhook_type not in WEBHOOK_COMMANDS:
        _LOGGER.error("Received invalid webhook type: %s", webhook_type)
        return empty_okay_response()

    _LOGGER.debug(
        "Received webhook payload for type %s: %s", webhook_type, webhook_payload
    )

    return await WEBHOOK_COMMANDS[webhook_type](hass, config_entry, webhook_payload)


@WEBHOOK_COMMANDS.register("call_service")
@validate_schema(
    {
        vol.Required(ATTR_DOMAIN): cv.string,
        vol.Required(ATTR_SERVICE): cv.string,
        vol.Optional(ATTR_SERVICE_DATA, default={}): dict,
    }
)
async def webhook_call_service(hass, config_entry, data):
    """Handle a call service webhook."""
    try:
        await hass.services.async_call(
            data[ATTR_DOMAIN],
            data[ATTR_SERVICE],
            data[ATTR_SERVICE_DATA],
            blocking=True,
            context=registration_context(config_entry.data),
        )
    except (vol.Invalid, ServiceNotFound, Exception) as ex:
        _LOGGER.error(
            "Error when calling service during mobile_app "
            "webhook (device name: %s): %s",
            config_entry.data[ATTR_DEVICE_NAME],
            ex,
        )
        raise HTTPBadRequest()

    return empty_okay_response()


@WEBHOOK_COMMANDS.register("fire_event")
@validate_schema(
    {
        vol.Required(ATTR_EVENT_TYPE): cv.string,
        vol.Optional(ATTR_EVENT_DATA, default={}): dict,
    }
)
async def webhook_fire_event(hass, config_entry, data):
    """Handle a fire event webhook."""
    event_type = data[ATTR_EVENT_TYPE]
    hass.bus.async_fire(
        event_type,
        data[ATTR_EVENT_DATA],
        EventOrigin.remote,
        context=registration_context(config_entry.data),
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("render_template")
@validate_schema(
    {
        str: {
            vol.Required(ATTR_TEMPLATE): cv.template,
            vol.Optional(ATTR_TEMPLATE_VARIABLES, default={}): dict,
        }
    }
)
async def webhook_render_template(hass, config_entry, data):
    """Handle a render template webhook."""
    resp = {}
    for key, item in data.items():
        try:
            tpl = item[ATTR_TEMPLATE]
            attach(hass, tpl)
            resp[key] = tpl.async_render(item.get(ATTR_TEMPLATE_VARIABLES))
        except TemplateError as ex:
            resp[key] = {"error": str(ex)}

    return webhook_response(resp, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("update_location")
@validate_schema(
    {
        vol.Optional(ATTR_LOCATION_NAME): cv.string,
        vol.Required(ATTR_GPS): cv.gps,
        vol.Required(ATTR_GPS_ACCURACY): cv.positive_int,
        vol.Optional(ATTR_BATTERY): cv.positive_int,
        vol.Optional(ATTR_SPEED): cv.positive_int,
        vol.Optional(ATTR_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_COURSE): cv.positive_int,
        vol.Optional(ATTR_VERTICAL_ACCURACY): cv.positive_int,
    }
)
async def webhook_update_location(hass, config_entry, data):
    """Handle an update location webhook."""
    hass.helpers.dispatcher.async_dispatcher_send(
        SIGNAL_LOCATION_UPDATE.format(config_entry.entry_id), data
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("update_registration")
@validate_schema(
    {
        vol.Optional(ATTR_APP_DATA, default={}): dict,
        vol.Required(ATTR_APP_VERSION): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_MANUFACTURER): cv.string,
        vol.Required(ATTR_MODEL): cv.string,
        vol.Optional(ATTR_OS_VERSION): cv.string,
    }
)
async def webhook_update_registration(hass, config_entry, data):
    """Handle an update registration webhook."""
    new_registration = {**config_entry.data, **data}

    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data[ATTR_DEVICE_ID])},
        manufacturer=new_registration[ATTR_MANUFACTURER],
        model=new_registration[ATTR_MODEL],
        name=new_registration[ATTR_DEVICE_NAME],
        sw_version=new_registration[ATTR_OS_VERSION],
    )

    hass.config_entries.async_update_entry(config_entry, data=new_registration)

    return webhook_response(
        safe_registration(new_registration), registration=new_registration,
    )


@WEBHOOK_COMMANDS.register("enable_encryption")
async def webhook_enable_encryption(hass, config_entry, data):
    """Handle a encryption enable webhook."""
    if config_entry.data[ATTR_SUPPORTS_ENCRYPTION]:
        _LOGGER.warning(
            "Refusing to enable encryption for %s because it is already enabled!",
            config_entry.data[ATTR_DEVICE_NAME],
        )
        return error_response(
            ERR_ENCRYPTION_ALREADY_ENABLED, "Encryption already enabled"
        )

    if not supports_encryption():
        _LOGGER.warning(
            "Unable to enable encryption for %s because libsodium is unavailable!",
            config_entry.data[ATTR_DEVICE_NAME],
        )
        return error_response(ERR_ENCRYPTION_NOT_AVAILABLE, "Encryption is unavailable")

    secret = secrets.token_hex(SecretBox.KEY_SIZE)

    data = {**config_entry.data, ATTR_SUPPORTS_ENCRYPTION: True, CONF_SECRET: secret}

    hass.config_entries.async_update_entry(config_entry, data=data)

    return json_response({"secret": secret})


@WEBHOOK_COMMANDS.register("register_sensor")
@validate_schema(
    {
        vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
        vol.Optional(ATTR_SENSOR_DEVICE_CLASS): vol.All(
            vol.Lower, vol.In(COMBINED_CLASSES)
        ),
        vol.Required(ATTR_SENSOR_NAME): cv.string,
        vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
        vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
        vol.Optional(ATTR_SENSOR_UOM): cv.string,
        vol.Required(ATTR_SENSOR_STATE): vol.Any(bool, str, int, float),
        vol.Optional(ATTR_SENSOR_ICON, default="mdi:cellphone"): cv.icon,
    }
)
async def webhook_register_sensor(hass, config_entry, data):
    """Handle a register sensor webhook."""
    entity_type = data[ATTR_SENSOR_TYPE]

    unique_id = data[ATTR_SENSOR_UNIQUE_ID]

    unique_store_key = f"{config_entry.data[CONF_WEBHOOK_ID]}_{unique_id}"

    if unique_store_key in hass.data[DOMAIN][entity_type]:
        _LOGGER.error("Refusing to re-register existing sensor %s!", unique_id)
        return error_response(
            ERR_SENSOR_DUPLICATE_UNIQUE_ID,
            f"{entity_type} {unique_id} already exists!",
            status=409,
        )

    data[CONF_WEBHOOK_ID] = config_entry.data[CONF_WEBHOOK_ID]

    hass.data[DOMAIN][entity_type][unique_store_key] = data

    try:
        await hass.data[DOMAIN][DATA_STORE].async_save(savable_state(hass))
    except HomeAssistantError as ex:
        _LOGGER.error("Error registering sensor: %s", ex)
        return empty_okay_response()

    register_signal = f"{DOMAIN}_{data[ATTR_SENSOR_TYPE]}_register"
    async_dispatcher_send(hass, register_signal, data)

    return webhook_response(
        {"success": True}, registration=config_entry.data, status=HTTP_CREATED,
    )


@WEBHOOK_COMMANDS.register("update_sensor_states")
@validate_schema(
    vol.All(
        cv.ensure_list,
        [
            # Partial schema, enough to identify schema.
            # We don't validate everything because otherwise 1 invalid sensor
            # will invalidate all sensors.
            vol.Schema(
                {
                    vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
                    vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
                },
                extra=vol.ALLOW_EXTRA,
            )
        ],
    )
)
async def webhook_update_sensor_states(hass, config_entry, data):
    """Handle an update sensor states webhook."""
    sensor_schema_full = vol.Schema(
        {
            vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
            vol.Optional(ATTR_SENSOR_ICON, default="mdi:cellphone"): cv.icon,
            vol.Required(ATTR_SENSOR_STATE): vol.Any(bool, str, int, float),
            vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
            vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
        }
    )

    resp = {}
    for sensor in data:
        entity_type = sensor[ATTR_SENSOR_TYPE]

        unique_id = sensor[ATTR_SENSOR_UNIQUE_ID]

        unique_store_key = f"{config_entry.data[CONF_WEBHOOK_ID]}_{unique_id}"

        if unique_store_key not in hass.data[DOMAIN][entity_type]:
            _LOGGER.error(
                "Refusing to update non-registered sensor: %s", unique_store_key
            )
            err_msg = f"{entity_type} {unique_id} is not registered"
            resp[unique_id] = {
                "success": False,
                "error": {"code": ERR_SENSOR_NOT_REGISTERED, "message": err_msg},
            }
            continue

        entry = hass.data[DOMAIN][entity_type][unique_store_key]

        try:
            sensor = sensor_schema_full(sensor)
        except vol.Invalid as err:
            err_msg = vol.humanize.humanize_error(sensor, err)
            _LOGGER.error(
                "Received invalid sensor payload for %s: %s", unique_id, err_msg
            )
            resp[unique_id] = {
                "success": False,
                "error": {"code": ERR_INVALID_FORMAT, "message": err_msg},
            }
            continue

        new_state = {**entry, **sensor}

        hass.data[DOMAIN][entity_type][unique_store_key] = new_state

        safe = savable_state(hass)

        try:
            await hass.data[DOMAIN][DATA_STORE].async_save(safe)
        except HomeAssistantError as ex:
            _LOGGER.error("Error updating mobile_app registration: %s", ex)
            return empty_okay_response()

        async_dispatcher_send(hass, SIGNAL_SENSOR_UPDATE, new_state)

        resp[unique_id] = {"success": True}

    return webhook_response(resp, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("get_zones")
async def webhook_get_zones(hass, config_entry, data):
    """Handle a get zones webhook."""
    zones = [
        hass.states.get(entity_id)
        for entity_id in sorted(hass.states.async_entity_ids(ZONE_DOMAIN))
    ]
    return webhook_response(zones, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("get_config")
async def webhook_get_config(hass, config_entry, data):
    """Handle a get config webhook."""
    hass_config = hass.config.as_dict()

    resp = {
        "latitude": hass_config["latitude"],
        "longitude": hass_config["longitude"],
        "elevation": hass_config["elevation"],
        "unit_system": hass_config["unit_system"],
        "location_name": hass_config["location_name"],
        "time_zone": hass_config["time_zone"],
        "components": hass_config["components"],
        "version": hass_config["version"],
        "theme_color": MANIFEST_JSON["theme_color"],
    }

    if CONF_CLOUDHOOK_URL in config_entry.data:
        resp[CONF_CLOUDHOOK_URL] = config_entry.data[CONF_CLOUDHOOK_URL]

    try:
        resp[CONF_REMOTE_UI_URL] = hass.components.cloud.async_remote_ui_url()
    except hass.components.cloud.CloudNotAvailable:
        pass

    return webhook_response(resp, registration=config_entry.data)
