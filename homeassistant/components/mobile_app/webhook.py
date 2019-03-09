"""Webhook handlers for mobile_app."""
from functools import partial
import logging
from typing import Dict

from aiohttp.web import HTTPBadRequest, json_response, Response, Request
import voluptuous as vol

from homeassistant.components.device_tracker import (DOMAIN as DT_DOMAIN,
                                                     SERVICE_SEE as DT_SEE)
from homeassistant.components.webhook import async_register as webhook_register

from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 CONF_WEBHOOK_ID, HTTP_BAD_REQUEST)
from homeassistant.core import EventOrigin
from homeassistant.exceptions import (HomeAssistantError, ServiceNotFound,
                                      TemplateError)
from homeassistant.helpers import template
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_APP_COMPONENT, DATA_DELETED_IDS,
                    ATTR_DEVICE_NAME, ATTR_EVENT_DATA, ATTR_EVENT_TYPE,
                    DATA_REGISTRATIONS, ATTR_TEMPLATE, ATTR_TEMPLATE_VARIABLES,
                    ATTR_WEBHOOK_DATA, ATTR_WEBHOOK_ENCRYPTED,
                    ATTR_WEBHOOK_ENCRYPTED_DATA, ATTR_WEBHOOK_TYPE,
                    CONF_SECRET, DOMAIN, WEBHOOK_PAYLOAD_SCHEMA,
                    WEBHOOK_SCHEMAS, WEBHOOK_TYPE_CALL_SERVICE,
                    WEBHOOK_TYPE_FIRE_EVENT, WEBHOOK_TYPE_RENDER_TEMPLATE,
                    WEBHOOK_TYPE_UPDATE_LOCATION,
                    WEBHOOK_TYPE_UPDATE_REGISTRATION)

from .helpers import (_decrypt_payload, empty_okay_response,
                      registration_context, safe_registration, savable_state)


_LOGGER = logging.getLogger(__name__)


def register_deleted_webhooks(hass: HomeAssistantType, store: Store):
    """Register previously deleted webhook IDs so we can return 410."""
    for deleted_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        try:
            webhook_register(hass, DOMAIN, "Deleted Webhook", deleted_id,
                             partial(handle_webhook, store))
        except ValueError:
            pass


def setup_registration(hass: HomeAssistantType, store: Store,
                       registration: Dict) -> None:
    """Register the webhook for a registration and loads the app component."""
    registration_name = 'Mobile App: {}'.format(registration[ATTR_DEVICE_NAME])
    webhook_id = registration[CONF_WEBHOOK_ID]
    webhook_register(hass, DOMAIN, registration_name, webhook_id,
                     partial(handle_webhook, store))

    if ATTR_APP_COMPONENT in registration:
        load_platform(hass, registration[ATTR_APP_COMPONENT], DOMAIN, {},
                      {DOMAIN: {}})


async def handle_webhook(store: Store, hass: HomeAssistantType,
                         webhook_id: str, request: Request) -> Response:
    """Handle webhook callback."""
    if webhook_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        return Response(status=410)

    headers = {}

    registration = hass.data[DOMAIN][DATA_REGISTRATIONS][webhook_id]

    try:
        req_data = await request.json()
    except ValueError:
        _LOGGER.warning('Received invalid JSON from mobile_app')
        return empty_okay_response(status=HTTP_BAD_REQUEST)

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
        try:
            tpl = template.Template(data[ATTR_TEMPLATE], hass)
            rendered = tpl.async_render(data.get(ATTR_TEMPLATE_VARIABLES))
            return json_response({"rendered": rendered}, headers=headers)
        # noqa: E722 pylint: disable=broad-except
        except (ValueError, TemplateError, Exception) as ex:
            _LOGGER.error("Error when rendering template during mobile_app "
                          "webhook (device name: %s): %s",
                          registration[ATTR_DEVICE_NAME], ex)
            return json_response(({"error": str(ex)}), status=HTTP_BAD_REQUEST,
                                 headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_LOCATION:
        try:
            await hass.services.async_call(DT_DOMAIN,
                                           DT_SEE, data,
                                           blocking=True, context=context)
        # noqa: E722 pylint: disable=broad-except
        except (vol.Invalid, ServiceNotFound, Exception) as ex:
            _LOGGER.error("Error when updating location during mobile_app "
                          "webhook (device name: %s): %s",
                          registration[ATTR_DEVICE_NAME], ex)
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_REGISTRATION:
        new_registration = {**registration, **data}

        hass.data[DOMAIN][DATA_REGISTRATIONS][webhook_id] = new_registration

        try:
            await store.async_save(savable_state(hass))
        except HomeAssistantError as ex:
            _LOGGER.error("Error updating mobile_app registration: %s", ex)
            return empty_okay_response()

        return json_response(safe_registration(new_registration))
