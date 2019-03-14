"""Webhook handlers for mobile_app."""
import logging

from aiohttp.web import HTTPBadRequest, Response, Request
import voluptuous as vol

from homeassistant.components.device_tracker import (ATTR_ATTRIBUTES,
                                                     ATTR_DEV_ID,
                                                     DOMAIN as DT_DOMAIN,
                                                     SERVICE_SEE as DT_SEE)

from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 CONF_WEBHOOK_ID, HTTP_BAD_REQUEST)
from homeassistant.core import EventOrigin
from homeassistant.exceptions import (ServiceNotFound, TemplateError)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.template import attach
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_ALTITUDE, ATTR_BATTERY, ATTR_COURSE, ATTR_DEVICE_ID,
                    ATTR_DEVICE_NAME, ATTR_EVENT_DATA, ATTR_EVENT_TYPE,
                    ATTR_GPS, ATTR_GPS_ACCURACY, ATTR_LOCATION_NAME,
                    ATTR_MANUFACTURER, ATTR_MODEL, ATTR_OS_VERSION, ATTR_SPEED,
                    ATTR_SUPPORTS_ENCRYPTION, ATTR_TEMPLATE,
                    ATTR_TEMPLATE_VARIABLES, ATTR_VERTICAL_ACCURACY,
                    ATTR_WEBHOOK_DATA, ATTR_WEBHOOK_ENCRYPTED,
                    ATTR_WEBHOOK_ENCRYPTED_DATA, ATTR_WEBHOOK_TYPE,
                    CONF_SECRET, DATA_CONFIG_ENTRIES, DATA_DELETED_IDS, DOMAIN,
                    ERR_ENCRYPTION_REQUIRED, WEBHOOK_PAYLOAD_SCHEMA,
                    WEBHOOK_SCHEMAS, WEBHOOK_TYPE_CALL_SERVICE,
                    WEBHOOK_TYPE_FIRE_EVENT, WEBHOOK_TYPE_RENDER_TEMPLATE,
                    WEBHOOK_TYPE_UPDATE_LOCATION,
                    WEBHOOK_TYPE_UPDATE_REGISTRATION)

from .helpers import (_decrypt_payload, empty_okay_response, error_response,
                      registration_context, safe_registration,
                      webhook_response)


_LOGGER = logging.getLogger(__name__)


async def handle_webhook(hass: HomeAssistantType, webhook_id: str,
                         request: Request) -> Response:
    """Handle webhook callback."""
    if webhook_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        return Response(status=410)

    headers = {}

    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]

    registration = config_entry.data

    try:
        req_data = await request.json()
    except ValueError:
        _LOGGER.warning('Received invalid JSON from mobile_app')
        return empty_okay_response(status=HTTP_BAD_REQUEST)

    if (ATTR_WEBHOOK_ENCRYPTED not in req_data and
            registration[ATTR_SUPPORTS_ENCRYPTION]):
        _LOGGER.warning("Refusing to accept unencrypted webhook from %s",
                        registration[ATTR_DEVICE_NAME])
        return error_response(ERR_ENCRYPTION_REQUIRED, "Encryption required")

    try:
        req_data = WEBHOOK_PAYLOAD_SCHEMA(req_data)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(req_data, ex)
        _LOGGER.error('Received invalid webhook payload: %s', err)
        return empty_okay_response()

    webhook_type = req_data[ATTR_WEBHOOK_TYPE]

    webhook_payload = req_data.get(ATTR_WEBHOOK_DATA, {})

    if req_data[ATTR_WEBHOOK_ENCRYPTED]:
        enc_data = req_data[ATTR_WEBHOOK_ENCRYPTED_DATA]
        webhook_payload = _decrypt_payload(registration[CONF_SECRET], enc_data)

    try:
        data = WEBHOOK_SCHEMAS[webhook_type](webhook_payload)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(webhook_payload, ex)
        _LOGGER.error('Received invalid webhook payload: %s', err)
        return empty_okay_response(headers=headers)

    context = registration_context(registration)

    if webhook_type == WEBHOOK_TYPE_CALL_SERVICE:
        try:
            await hass.services.async_call(data[ATTR_DOMAIN],
                                           data[ATTR_SERVICE],
                                           data[ATTR_SERVICE_DATA],
                                           blocking=True, context=context)
        # noqa: E722 pylint: disable=broad-except
        except (vol.Invalid, ServiceNotFound, Exception) as ex:
            _LOGGER.error("Error when calling service during mobile_app "
                          "webhook (device name: %s): %s",
                          registration[ATTR_DEVICE_NAME], ex)
            raise HTTPBadRequest()

        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_FIRE_EVENT:
        event_type = data[ATTR_EVENT_TYPE]
        hass.bus.async_fire(event_type, data[ATTR_EVENT_DATA],
                            EventOrigin.remote,
                            context=context)
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_RENDER_TEMPLATE:
        resp = {}
        for key, item in data.items():
            try:
                tpl = item[ATTR_TEMPLATE]
                attach(hass, tpl)
                resp[key] = tpl.async_render(item.get(ATTR_TEMPLATE_VARIABLES))
            # noqa: E722 pylint: disable=broad-except
            except TemplateError as ex:
                resp[key] = {"error": str(ex)}

        return webhook_response(resp, registration=registration,
                                headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_LOCATION:
        see_payload = {
            ATTR_DEV_ID: registration[ATTR_DEVICE_ID],
            ATTR_LOCATION_NAME: data.get(ATTR_LOCATION_NAME),
            ATTR_GPS: data.get(ATTR_GPS),
            ATTR_GPS_ACCURACY: data.get(ATTR_GPS_ACCURACY),
            ATTR_BATTERY: data.get(ATTR_BATTERY),
            ATTR_ATTRIBUTES: {
                ATTR_SPEED: data.get(ATTR_SPEED),
                ATTR_ALTITUDE: data.get(ATTR_ALTITUDE),
                ATTR_COURSE: data.get(ATTR_COURSE),
                ATTR_VERTICAL_ACCURACY: data.get(ATTR_VERTICAL_ACCURACY),
            }
        }

        try:
            await hass.services.async_call(DT_DOMAIN,
                                           DT_SEE, see_payload,
                                           blocking=True, context=context)
        # noqa: E722 pylint: disable=broad-except
        except (vol.Invalid, ServiceNotFound, Exception) as ex:
            _LOGGER.error("Error when updating location during mobile_app "
                          "webhook (device name: %s): %s",
                          registration[ATTR_DEVICE_NAME], ex)
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_REGISTRATION:
        new_registration = {**registration, **data}

        device_registry = await dr.async_get_registry(hass)

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={
                (ATTR_DEVICE_ID, registration[ATTR_DEVICE_ID]),
                (CONF_WEBHOOK_ID, registration[CONF_WEBHOOK_ID])
            },
            manufacturer=new_registration[ATTR_MANUFACTURER],
            model=new_registration[ATTR_MODEL],
            name=new_registration[ATTR_DEVICE_NAME],
            sw_version=new_registration[ATTR_OS_VERSION]
        )

        hass.config_entries.async_update_entry(config_entry,
                                               data=new_registration)

        return webhook_response(safe_registration(new_registration),
                                registration=registration, headers=headers)
