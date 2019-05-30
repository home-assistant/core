"""Webhook handlers for mobile_app."""
import logging

from aiohttp.web import HTTPBadRequest, Response, Request
import voluptuous as vol

from homeassistant.components.cloud import (async_remote_ui_url,
                                            CloudNotAvailable)
from homeassistant.components.device_tracker import (ATTR_ATTRIBUTES,
                                                     ATTR_DEV_ID,
                                                     DOMAIN as DT_DOMAIN,
                                                     SERVICE_SEE as DT_SEE)
from homeassistant.components.frontend import MANIFEST_JSON
from homeassistant.components.zone.const import DOMAIN as ZONE_DOMAIN

from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 CONF_WEBHOOK_ID, HTTP_BAD_REQUEST,
                                 HTTP_CREATED)
from homeassistant.core import EventOrigin
from homeassistant.exceptions import (HomeAssistantError,
                                      ServiceNotFound, TemplateError)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.template import attach
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_ALTITUDE, ATTR_BATTERY, ATTR_COURSE, ATTR_DEVICE_ID,
                    ATTR_DEVICE_NAME, ATTR_EVENT_DATA, ATTR_EVENT_TYPE,
                    ATTR_GPS, ATTR_GPS_ACCURACY, ATTR_LOCATION_NAME,
                    ATTR_MANUFACTURER, ATTR_MODEL, ATTR_OS_VERSION,
                    ATTR_SENSOR_TYPE, ATTR_SENSOR_UNIQUE_ID, ATTR_SPEED,
                    ATTR_SUPPORTS_ENCRYPTION, ATTR_TEMPLATE,
                    ATTR_TEMPLATE_VARIABLES, ATTR_VERTICAL_ACCURACY,
                    ATTR_WEBHOOK_DATA, ATTR_WEBHOOK_ENCRYPTED,
                    ATTR_WEBHOOK_ENCRYPTED_DATA, ATTR_WEBHOOK_TYPE,
                    CONF_CLOUDHOOK_URL, CONF_REMOTE_UI_URL, CONF_SECRET,
                    DATA_CONFIG_ENTRIES, DATA_DELETED_IDS, DATA_STORE, DOMAIN,
                    ERR_ENCRYPTION_REQUIRED, ERR_SENSOR_DUPLICATE_UNIQUE_ID,
                    ERR_SENSOR_NOT_REGISTERED, SIGNAL_SENSOR_UPDATE,
                    WEBHOOK_PAYLOAD_SCHEMA, WEBHOOK_SCHEMAS, WEBHOOK_TYPES,
                    WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                    WEBHOOK_TYPE_GET_CONFIG, WEBHOOK_TYPE_GET_ZONES,
                    WEBHOOK_TYPE_REGISTER_SENSOR, WEBHOOK_TYPE_RENDER_TEMPLATE,
                    WEBHOOK_TYPE_UPDATE_LOCATION,
                    WEBHOOK_TYPE_UPDATE_REGISTRATION,
                    WEBHOOK_TYPE_UPDATE_SENSOR_STATES)


from .helpers import (_decrypt_payload, empty_okay_response, error_response,
                      registration_context, safe_registration, savable_state,
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

    if webhook_type not in WEBHOOK_TYPES:
        _LOGGER.error('Received invalid webhook type: %s', webhook_type)
        return empty_okay_response()

    data = webhook_payload

    _LOGGER.debug("Received webhook payload for type %s: %s", webhook_type,
                  data)

    if webhook_type in WEBHOOK_SCHEMAS:
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
            ATTR_GPS: data[ATTR_GPS],
            ATTR_GPS_ACCURACY: data[ATTR_GPS_ACCURACY],
        }

        for key in (ATTR_LOCATION_NAME, ATTR_BATTERY):
            value = data.get(key)
            if value is not None:
                see_payload[key] = value

        attrs = {}

        for key in (ATTR_ALTITUDE, ATTR_COURSE,
                    ATTR_SPEED, ATTR_VERTICAL_ACCURACY):
            value = data.get(key)
            if value is not None:
                attrs[key] = value

        if attrs:
            see_payload[ATTR_ATTRIBUTES] = attrs

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

    if webhook_type == WEBHOOK_TYPE_REGISTER_SENSOR:
        entity_type = data[ATTR_SENSOR_TYPE]

        unique_id = data[ATTR_SENSOR_UNIQUE_ID]

        unique_store_key = "{}_{}".format(webhook_id, unique_id)

        if unique_store_key in hass.data[DOMAIN][entity_type]:
            _LOGGER.error("Refusing to re-register existing sensor %s!",
                          unique_id)
            return error_response(ERR_SENSOR_DUPLICATE_UNIQUE_ID,
                                  "{} {} already exists!".format(entity_type,
                                                                 unique_id),
                                  status=409)

        data[CONF_WEBHOOK_ID] = webhook_id

        hass.data[DOMAIN][entity_type][unique_store_key] = data

        try:
            await hass.data[DOMAIN][DATA_STORE].async_save(savable_state(hass))
        except HomeAssistantError as ex:
            _LOGGER.error("Error registering sensor: %s", ex)
            return empty_okay_response()

        register_signal = '{}_{}_register'.format(DOMAIN,
                                                  data[ATTR_SENSOR_TYPE])
        async_dispatcher_send(hass, register_signal, data)

        return webhook_response({'success': True},
                                registration=registration, status=HTTP_CREATED,
                                headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_SENSOR_STATES:
        resp = {}
        for sensor in data:
            entity_type = sensor[ATTR_SENSOR_TYPE]

            unique_id = sensor[ATTR_SENSOR_UNIQUE_ID]

            unique_store_key = "{}_{}".format(webhook_id, unique_id)

            if unique_store_key not in hass.data[DOMAIN][entity_type]:
                _LOGGER.error("Refusing to update non-registered sensor: %s",
                              unique_store_key)
                err_msg = '{} {} is not registered'.format(entity_type,
                                                           unique_id)
                resp[unique_id] = {
                    'success': False,
                    'error': {
                        'code': ERR_SENSOR_NOT_REGISTERED,
                        'message': err_msg
                    }
                }
                continue

            entry = hass.data[DOMAIN][entity_type][unique_store_key]

            new_state = {**entry, **sensor}

            hass.data[DOMAIN][entity_type][unique_store_key] = new_state

            safe = savable_state(hass)

            try:
                await hass.data[DOMAIN][DATA_STORE].async_save(safe)
            except HomeAssistantError as ex:
                _LOGGER.error("Error updating mobile_app registration: %s", ex)
                return empty_okay_response()

            async_dispatcher_send(hass, SIGNAL_SENSOR_UPDATE, new_state)

            resp[unique_id] = {'success': True}

        return webhook_response(resp, registration=registration,
                                headers=headers)

    if webhook_type == WEBHOOK_TYPE_GET_ZONES:
        zones = (hass.states.get(entity_id) for entity_id
                 in sorted(hass.states.async_entity_ids(ZONE_DOMAIN)))
        return webhook_response(list(zones), registration=registration,
                                headers=headers)

    if webhook_type == WEBHOOK_TYPE_GET_CONFIG:

        hass_config = hass.config.as_dict()

        resp = {
            'latitude': hass_config['latitude'],
            'longitude': hass_config['longitude'],
            'elevation': hass_config['elevation'],
            'unit_system': hass_config['unit_system'],
            'location_name': hass_config['location_name'],
            'time_zone': hass_config['time_zone'],
            'components': hass_config['components'],
            'version': hass_config['version'],
            'theme_color': MANIFEST_JSON['theme_color'],
        }

        if CONF_CLOUDHOOK_URL in registration:
            resp[CONF_CLOUDHOOK_URL] = registration[CONF_CLOUDHOOK_URL]

        try:
            resp[CONF_REMOTE_UI_URL] = async_remote_ui_url(hass)
        except CloudNotAvailable:
            pass

        return webhook_response(resp, registration=registration,
                                headers=headers)
