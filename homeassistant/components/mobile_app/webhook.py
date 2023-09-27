"""Webhook handlers for mobile_app."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
from functools import lru_cache, wraps
from http import HTTPStatus
import logging
import secrets
from typing import Any

from aiohttp.web import HTTPBadRequest, Request, Response, json_response
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox
import voluptuous as vol

from homeassistant.components import (
    camera,
    cloud,
    conversation,
    notify as hass_notify,
    tag,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.device_tracker import (
    ATTR_BATTERY,
    ATTR_GPS,
    ATTR_GPS_ACCURACY,
    ATTR_LOCATION_NAME,
)
from homeassistant.components.frontend import MANIFEST_JSON
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_WEBHOOK_ID,
    EntityCategory,
)
from homeassistant.core import EventOrigin, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound, TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    template,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.decorator import Registry

from .const import (
    ATTR_ALTITUDE,
    ATTR_APP_DATA,
    ATTR_APP_VERSION,
    ATTR_CAMERA_ENTITY_ID,
    ATTR_COURSE,
    ATTR_DEVICE_NAME,
    ATTR_EVENT_DATA,
    ATTR_EVENT_TYPE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NO_LEGACY_ENCRYPTION,
    ATTR_OS_VERSION,
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_DISABLED,
    ATTR_SENSOR_ENTITY_CATEGORY,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_NAME,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_STATE_CLASS,
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
    DATA_DEVICES,
    DOMAIN,
    ERR_ENCRYPTION_ALREADY_ENABLED,
    ERR_ENCRYPTION_NOT_AVAILABLE,
    ERR_ENCRYPTION_REQUIRED,
    ERR_INVALID_FORMAT,
    ERR_SENSOR_NOT_REGISTERED,
    SCHEMA_APP_DATA,
    SIGNAL_LOCATION_UPDATE,
    SIGNAL_SENSOR_UPDATE,
)
from .helpers import (
    decrypt_payload,
    decrypt_payload_legacy,
    empty_okay_response,
    error_response,
    registration_context,
    safe_registration,
    supports_encryption,
    webhook_response,
)

_LOGGER = logging.getLogger(__name__)

DELAY_SAVE = 10

WEBHOOK_COMMANDS: Registry[
    str, Callable[[HomeAssistant, ConfigEntry, Any], Coroutine[Any, Any, Response]]
] = Registry()

SENSOR_TYPES = (ATTR_SENSOR_TYPE_BINARY_SENSOR, ATTR_SENSOR_TYPE_SENSOR)

WEBHOOK_PAYLOAD_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Required(ATTR_WEBHOOK_TYPE): cv.string,
            vol.Optional(ATTR_WEBHOOK_DATA): vol.Any(dict, list),
        }
    ),
    vol.Schema(
        {
            vol.Required(ATTR_WEBHOOK_TYPE): cv.string,
            vol.Required(ATTR_WEBHOOK_ENCRYPTED): True,
            vol.Optional(ATTR_WEBHOOK_ENCRYPTED_DATA): cv.string,
        }
    ),
)

SENSOR_SCHEMA_FULL = vol.Schema(
    {
        vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
        vol.Optional(ATTR_SENSOR_ICON, default="mdi:cellphone"): vol.Any(None, cv.icon),
        vol.Required(ATTR_SENSOR_STATE): vol.Any(None, bool, int, float, str),
        vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
        vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
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
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle webhook callback."""
    if webhook_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        return Response(status=410)

    config_entry: ConfigEntry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]

    device_name: str = config_entry.data[ATTR_DEVICE_NAME]

    try:
        req_data = await request.json()
    except ValueError:
        _LOGGER.warning("Received invalid JSON from mobile_app device: %s", device_name)
        return empty_okay_response(status=HTTPStatus.BAD_REQUEST)

    if (
        ATTR_WEBHOOK_ENCRYPTED not in req_data
        and config_entry.data[ATTR_SUPPORTS_ENCRYPTION]
    ):
        _LOGGER.warning(
            "Refusing to accept unencrypted webhook from %s",
            device_name,
        )
        return error_response(ERR_ENCRYPTION_REQUIRED, "Encryption required")

    try:
        req_data = WEBHOOK_PAYLOAD_SCHEMA(req_data)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(req_data, ex)
        _LOGGER.error(
            "Received invalid webhook from %s with payload: %s", device_name, err
        )
        return empty_okay_response()

    webhook_type = req_data[ATTR_WEBHOOK_TYPE]

    webhook_payload = None

    if ATTR_WEBHOOK_ENCRYPTED in req_data:
        enc_data = req_data[ATTR_WEBHOOK_ENCRYPTED_DATA]
        try:
            webhook_payload = decrypt_payload(config_entry.data[CONF_SECRET], enc_data)
            if ATTR_NO_LEGACY_ENCRYPTION not in config_entry.data:
                data = {**config_entry.data, ATTR_NO_LEGACY_ENCRYPTION: True}
                hass.config_entries.async_update_entry(config_entry, data=data)
        except CryptoError:
            if ATTR_NO_LEGACY_ENCRYPTION not in config_entry.data:
                try:
                    webhook_payload = decrypt_payload_legacy(
                        config_entry.data[CONF_SECRET], enc_data
                    )
                except CryptoError:
                    _LOGGER.warning(
                        "Ignoring encrypted payload because unable to decrypt"
                    )
                except ValueError:
                    _LOGGER.warning("Ignoring invalid JSON in encrypted payload")
            else:
                _LOGGER.warning("Ignoring encrypted payload because unable to decrypt")
        except ValueError as err:
            _LOGGER.warning("Ignoring invalid JSON in encrypted payload: %s", err)
    else:
        webhook_payload = req_data.get(ATTR_WEBHOOK_DATA, {})

    if webhook_payload is None:
        return empty_okay_response()

    if webhook_type not in WEBHOOK_COMMANDS:
        _LOGGER.error(
            "Received invalid webhook from %s of type: %s", device_name, webhook_type
        )
        return empty_okay_response()

    _LOGGER.debug(
        "Received webhook payload from %s for type %s: %s",
        device_name,
        webhook_type,
        webhook_payload,
    )

    # Shield so we make sure we finish the webhook, even if sender hangs up.
    return await asyncio.shield(
        WEBHOOK_COMMANDS[webhook_type](hass, config_entry, webhook_payload)
    )


@WEBHOOK_COMMANDS.register("call_service")
@validate_schema(
    {
        vol.Required(ATTR_DOMAIN): cv.string,
        vol.Required(ATTR_SERVICE): cv.string,
        vol.Optional(ATTR_SERVICE_DATA, default={}): dict,
    }
)
async def webhook_call_service(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
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
            (
                "Error when calling service during mobile_app "
                "webhook (device name: %s): %s"
            ),
            config_entry.data[ATTR_DEVICE_NAME],
            ex,
        )
        raise HTTPBadRequest() from ex

    return empty_okay_response()


@WEBHOOK_COMMANDS.register("fire_event")
@validate_schema(
    {
        vol.Required(ATTR_EVENT_TYPE): cv.string,
        vol.Optional(ATTR_EVENT_DATA, default={}): dict,
    }
)
async def webhook_fire_event(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle a fire event webhook."""
    event_type: str = data[ATTR_EVENT_TYPE]
    hass.bus.async_fire(
        event_type,
        data[ATTR_EVENT_DATA],
        EventOrigin.remote,
        context=registration_context(config_entry.data),
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("conversation_process")
@validate_schema(
    {
        vol.Required("text"): cv.string,
        vol.Optional("language"): cv.string,
        vol.Optional("conversation_id"): cv.string,
    }
)
async def webhook_conversation_process(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle a conversation process webhook."""
    result = await conversation.async_converse(
        hass,
        text=data["text"],
        language=data.get("language"),
        conversation_id=data.get("conversation_id"),
        context=registration_context(config_entry.data),
        device_id=config_entry.data[ATTR_DEVICE_ID],
    )
    return webhook_response(result.as_dict(), registration=config_entry.data)


@WEBHOOK_COMMANDS.register("stream_camera")
@validate_schema({vol.Required(ATTR_CAMERA_ENTITY_ID): cv.string})
async def webhook_stream_camera(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
) -> Response:
    """Handle a request to HLS-stream a camera."""
    if (camera_state := hass.states.get(data[ATTR_CAMERA_ENTITY_ID])) is None:
        return webhook_response(
            {"success": False},
            registration=config_entry.data,
            status=HTTPStatus.BAD_REQUEST,
        )

    resp: dict[str, Any] = {
        "mjpeg_path": f"/api/camera_proxy_stream/{camera_state.entity_id}"
    }

    if camera_state.attributes[ATTR_SUPPORTED_FEATURES] & CameraEntityFeature.STREAM:
        try:
            resp["hls_path"] = await camera.async_request_stream(
                hass, camera_state.entity_id, "hls"
            )
        except HomeAssistantError:
            resp["hls_path"] = None
    else:
        resp["hls_path"] = None

    return webhook_response(resp, registration=config_entry.data)


@lru_cache
def _cached_template(template_str: str, hass: HomeAssistant) -> template.Template:
    """Return a cached template."""
    return template.Template(template_str, hass)


@WEBHOOK_COMMANDS.register("render_template")
@validate_schema(
    {
        str: {
            vol.Required(ATTR_TEMPLATE): cv.string,
            vol.Optional(ATTR_TEMPLATE_VARIABLES, default={}): dict,
        }
    }
)
async def webhook_render_template(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle a render template webhook."""
    resp = {}
    for key, item in data.items():
        try:
            tpl = _cached_template(item[ATTR_TEMPLATE], hass)
            resp[key] = tpl.async_render(item.get(ATTR_TEMPLATE_VARIABLES))
        except TemplateError as ex:
            resp[key] = {"error": str(ex)}

    return webhook_response(resp, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("update_location")
@validate_schema(
    vol.Schema(
        cv.key_dependency(ATTR_GPS, ATTR_GPS_ACCURACY),
        {
            vol.Optional(ATTR_LOCATION_NAME): cv.string,
            vol.Optional(ATTR_GPS): cv.gps,
            vol.Optional(ATTR_GPS_ACCURACY): cv.positive_int,
            vol.Optional(ATTR_BATTERY): cv.positive_int,
            vol.Optional(ATTR_SPEED): cv.positive_int,
            vol.Optional(ATTR_ALTITUDE): vol.Coerce(float),
            vol.Optional(ATTR_COURSE): cv.positive_int,
            vol.Optional(ATTR_VERTICAL_ACCURACY): cv.positive_int,
        },
    )
)
async def webhook_update_location(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle an update location webhook."""
    async_dispatcher_send(
        hass, SIGNAL_LOCATION_UPDATE.format(config_entry.entry_id), data
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("update_registration")
@validate_schema(
    {
        vol.Optional(ATTR_APP_DATA): SCHEMA_APP_DATA,
        vol.Required(ATTR_APP_VERSION): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_MANUFACTURER): cv.string,
        vol.Required(ATTR_MODEL): cv.string,
        vol.Optional(ATTR_OS_VERSION): cv.string,
    }
)
async def webhook_update_registration(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle an update registration webhook."""
    new_registration = {**config_entry.data, **data}

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data[ATTR_DEVICE_ID])},
        manufacturer=new_registration[ATTR_MANUFACTURER],
        model=new_registration[ATTR_MODEL],
        name=new_registration[ATTR_DEVICE_NAME],
        sw_version=new_registration[ATTR_OS_VERSION],
    )

    hass.config_entries.async_update_entry(config_entry, data=new_registration)

    await hass_notify.async_reload(hass, DOMAIN)

    return webhook_response(
        safe_registration(new_registration),
        registration=new_registration,
    )


@WEBHOOK_COMMANDS.register("enable_encryption")
async def webhook_enable_encryption(
    hass: HomeAssistant, config_entry: ConfigEntry, data: Any
) -> Response:
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

    update_data = {
        **config_entry.data,
        ATTR_SUPPORTS_ENCRYPTION: True,
        CONF_SECRET: secret,
    }

    hass.config_entries.async_update_entry(config_entry, data=update_data)

    return json_response({"secret": secret})


def _validate_state_class_sensor(value: dict[str, Any]) -> dict[str, Any]:
    """Validate we only set state class for sensors."""
    if (
        ATTR_SENSOR_STATE_CLASS in value
        and value[ATTR_SENSOR_TYPE] != ATTR_SENSOR_TYPE_SENSOR
    ):
        raise vol.Invalid("state_class only allowed for sensors")

    return value


def _gen_unique_id(webhook_id: str, sensor_unique_id: str) -> str:
    """Return a unique sensor ID."""
    return f"{webhook_id}_{sensor_unique_id}"


def _extract_sensor_unique_id(webhook_id: str, unique_id: str) -> str:
    """Return a unique sensor ID."""
    return unique_id[len(webhook_id) + 1 :]


@WEBHOOK_COMMANDS.register("register_sensor")
@validate_schema(
    vol.All(
        {
            vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
            vol.Optional(ATTR_SENSOR_DEVICE_CLASS): vol.Any(
                None,
                vol.All(vol.Lower, vol.Coerce(BinarySensorDeviceClass)),
                vol.All(vol.Lower, vol.Coerce(SensorDeviceClass)),
            ),
            vol.Required(ATTR_SENSOR_NAME): cv.string,
            vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
            vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
            vol.Optional(ATTR_SENSOR_UOM): vol.Any(None, cv.string),
            vol.Optional(ATTR_SENSOR_STATE, default=None): vol.Any(
                None, bool, int, float, str
            ),
            vol.Optional(ATTR_SENSOR_ENTITY_CATEGORY): vol.Any(
                None, vol.Coerce(EntityCategory)
            ),
            vol.Optional(ATTR_SENSOR_ICON, default="mdi:cellphone"): vol.Any(
                None, cv.icon
            ),
            vol.Optional(ATTR_SENSOR_STATE_CLASS): vol.Any(
                None, vol.Coerce(SensorStateClass)
            ),
            vol.Optional(ATTR_SENSOR_DISABLED): bool,
        },
        _validate_state_class_sensor,
    )
)
async def webhook_register_sensor(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Handle a register sensor webhook."""
    entity_type: str = data[ATTR_SENSOR_TYPE]
    unique_id: str = data[ATTR_SENSOR_UNIQUE_ID]
    device_name: str = config_entry.data[ATTR_DEVICE_NAME]

    unique_store_key = _gen_unique_id(config_entry.data[CONF_WEBHOOK_ID], unique_id)
    entity_registry = er.async_get(hass)
    existing_sensor = entity_registry.async_get_entity_id(
        entity_type, DOMAIN, unique_store_key
    )

    data[CONF_WEBHOOK_ID] = config_entry.data[CONF_WEBHOOK_ID]

    # If sensor already is registered, update current state instead
    if existing_sensor:
        _LOGGER.debug(
            "Re-register for %s of existing sensor %s", device_name, unique_id
        )

        entry = entity_registry.async_get(existing_sensor)
        assert entry is not None
        changes: dict[str, Any] = {}

        if (
            new_name := f"{device_name} {data[ATTR_SENSOR_NAME]}"
        ) != entry.original_name:
            changes["original_name"] = new_name

        if (
            should_be_disabled := data.get(ATTR_SENSOR_DISABLED)
        ) is None or should_be_disabled == entry.disabled:
            pass
        elif should_be_disabled:
            changes["disabled_by"] = er.RegistryEntryDisabler.INTEGRATION
        else:
            changes["disabled_by"] = None

        for ent_reg_key, data_key in (
            ("device_class", ATTR_SENSOR_DEVICE_CLASS),
            ("unit_of_measurement", ATTR_SENSOR_UOM),
            ("entity_category", ATTR_SENSOR_ENTITY_CATEGORY),
            ("original_icon", ATTR_SENSOR_ICON),
        ):
            if data_key in data and getattr(entry, ent_reg_key) != data[data_key]:
                changes[ent_reg_key] = data[data_key]

        if changes:
            entity_registry.async_update_entity(existing_sensor, **changes)

        async_dispatcher_send(hass, SIGNAL_SENSOR_UPDATE, unique_store_key, data)
    else:
        data[CONF_UNIQUE_ID] = unique_store_key
        data[
            CONF_NAME
        ] = f"{config_entry.data[ATTR_DEVICE_NAME]} {data[ATTR_SENSOR_NAME]}"

        register_signal = f"{DOMAIN}_{data[ATTR_SENSOR_TYPE]}_register"
        async_dispatcher_send(hass, register_signal, data)

    return webhook_response(
        {"success": True},
        registration=config_entry.data,
        status=HTTPStatus.CREATED,
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
async def webhook_update_sensor_states(
    hass: HomeAssistant, config_entry: ConfigEntry, data: list[dict[str, Any]]
) -> Response:
    """Handle an update sensor states webhook."""
    device_name: str = config_entry.data[ATTR_DEVICE_NAME]
    resp: dict[str, Any] = {}
    entity_registry = er.async_get(hass)

    for sensor in data:
        entity_type: str = sensor[ATTR_SENSOR_TYPE]

        unique_id: str = sensor[ATTR_SENSOR_UNIQUE_ID]

        unique_store_key = _gen_unique_id(config_entry.data[CONF_WEBHOOK_ID], unique_id)

        if not (
            entity_id := entity_registry.async_get_entity_id(
                entity_type, DOMAIN, unique_store_key
            )
        ):
            _LOGGER.debug(
                "Refusing to update %s non-registered sensor: %s",
                device_name,
                unique_store_key,
            )
            err_msg = f"{entity_type} {unique_id} is not registered"
            resp[unique_id] = {
                "success": False,
                "error": {"code": ERR_SENSOR_NOT_REGISTERED, "message": err_msg},
            }
            continue

        try:
            sensor = SENSOR_SCHEMA_FULL(sensor)
        except vol.Invalid as err:
            err_msg = vol.humanize.humanize_error(sensor, err)
            _LOGGER.error(
                "Received invalid sensor payload from %s for %s: %s",
                device_name,
                unique_id,
                err_msg,
            )
            resp[unique_id] = {
                "success": False,
                "error": {"code": ERR_INVALID_FORMAT, "message": err_msg},
            }
            continue

        sensor[CONF_WEBHOOK_ID] = config_entry.data[CONF_WEBHOOK_ID]
        async_dispatcher_send(
            hass,
            SIGNAL_SENSOR_UPDATE,
            unique_store_key,
            sensor,
        )

        resp[unique_id] = {"success": True}

        # Check if disabled
        entry = entity_registry.async_get(entity_id)

        if entry and entry.disabled_by:
            resp[unique_id]["is_disabled"] = True

    return webhook_response(resp, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("get_zones")
async def webhook_get_zones(
    hass: HomeAssistant, config_entry: ConfigEntry, data: Any
) -> Response:
    """Handle a get zones webhook."""
    zones = [
        hass.states.get(entity_id)
        for entity_id in sorted(hass.states.async_entity_ids(ZONE_DOMAIN))
    ]
    return webhook_response(zones, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("get_config")
async def webhook_get_config(
    hass: HomeAssistant, config_entry: ConfigEntry, data: Any
) -> Response:
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

    if cloud.async_active_subscription(hass):
        with suppress(hass.components.cloud.CloudNotAvailable):
            resp[CONF_REMOTE_UI_URL] = cloud.async_remote_ui_url(hass)

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    entities = {}
    for entry in er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    ):
        if entry.domain in ("binary_sensor", "sensor"):
            unique_id = _extract_sensor_unique_id(webhook_id, entry.unique_id)
        else:
            unique_id = entry.unique_id

        entities[unique_id] = {"disabled": entry.disabled}

    resp["entities"] = entities

    return webhook_response(resp, registration=config_entry.data)


@WEBHOOK_COMMANDS.register("scan_tag")
@validate_schema({vol.Required("tag_id"): cv.string})
async def webhook_scan_tag(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
) -> Response:
    """Handle a fire event webhook."""
    await tag.async_scan_tag(
        hass,
        data["tag_id"],
        hass.data[DOMAIN][DATA_DEVICES][config_entry.data[CONF_WEBHOOK_ID]].id,
        registration_context(config_entry.data),
    )
    return empty_okay_response()
