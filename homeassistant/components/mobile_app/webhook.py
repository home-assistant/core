"""Webhook handlers for mobile_app."""
from functools import partial
import logging
from typing import Dict

from aiohttp.web import HTTPBadRequest, json_response, Response, Request
import voluptuous as vol

from homeassistant.components.cloud import (async_create_cloudhook,
                                            async_is_logged_in,
                                            CloudNotAvailable,
                                            is_cloudhook_request)
from homeassistant.components.device_tracker import (DOMAIN as DT_DOMAIN,
                                                     SERVICE_SEE as DT_SEE)
from homeassistant.components.webhook import async_register as webhook_register

from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 CONF_WEBHOOK_ID, HTTP_BAD_REQUEST)
from homeassistant.core import EventOrigin
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers import template
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import (HomeAssistantError, ServiceNotFound,
                                      TemplateError)

from .const import (ATTR_APP_ID, ATTR_APP_NAME, ATTR_DELETED_IDS,
                    ATTR_DEVICE_NAME, ATTR_EVENT_DATA, ATTR_EVENT_TYPE,
                    ATTR_REGISTRATIONS, ATTR_SUPPORTS_ENCRYPTION,
                    ATTR_TEMPLATE, ATTR_TEMPLATE_VARIABLES, ATTR_WEBHOOK_DATA,
                    ATTR_WEBHOOK_ENCRYPTED, ATTR_WEBHOOK_ENCRYPTED_DATA,
                    ATTR_WEBHOOK_TYPE, CONF_CLOUDHOOK_ID, CONF_CLOUDHOOK_URL,
                    CONF_SECRET, CONF_USER_ID, DOMAIN,
                    HTTP_X_CLOUD_HOOK_ID, HTTP_X_CLOUD_HOOK_URL,
                    WEBHOOK_PAYLOAD_SCHEMA, WEBHOOK_SCHEMAS,
                    WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                    WEBHOOK_TYPE_RENDER_TEMPLATE, WEBHOOK_TYPE_UPDATE_LOCATION,
                    WEBHOOK_TYPE_UPDATE_REGISTRATION)

from .helpers import (device_context, _decrypt_payload, empty_okay_response,
                      safe_device, savable_state)


_LOGGER = logging.getLogger(__name__)


def register_device_webhook(hass: HomeAssistantType, store: Store,
                            device: Dict) -> None:
    """Register the webhook for a device."""
    device_name = 'Mobile App: {}'.format(device[ATTR_DEVICE_NAME])
    webhook_id = device[CONF_WEBHOOK_ID]
    webhook_register(hass, DOMAIN, device_name, webhook_id,
                     partial(handle_webhook, store))


async def handle_webhook(store: Store, hass: HomeAssistantType,
                         webhook_id: str, request: Request) -> Response:
    """Handle webhook callback."""
    if webhook_id in hass.data[DOMAIN][ATTR_DELETED_IDS]:
        return Response(status=410)

    device = hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id]

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
        return empty_okay_response()

    headers = {}

    via_cloud = is_cloudhook_request(request)

    _LOGGER.error("HASS %s", async_is_logged_in(hass))

    logged_in = async_is_logged_in(hass)

    if via_cloud is False and logged_in is True:
        cloud_id = device.get(CONF_CLOUDHOOK_ID)
        cloud_url = device.get(CONF_CLOUDHOOK_URL)
        if cloud_url is None:
            try:
                hook = await async_create_cloudhook(hass, webhook_id)
                cloud_id = hook[CONF_CLOUDHOOK_ID]
                cloud_url = hook[CONF_CLOUDHOOK_URL]
            except CloudNotAvailable:
                _LOGGER.error("Error creating cloudhook during local call")

        headers[HTTP_X_CLOUD_HOOK_ID] = cloud_id
        headers[HTTP_X_CLOUD_HOOK_URL] = cloud_url

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
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_CALL_SERVICE:
        try:
            await hass.services.async_call(data[ATTR_DOMAIN],
                                           data[ATTR_SERVICE],
                                           data[ATTR_SERVICE_DATA],
                                           blocking=True,
                                           context=device_context(device))
        except (vol.Invalid, ServiceNotFound):
            raise HTTPBadRequest()

        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_FIRE_EVENT:
        event_type = data[ATTR_EVENT_TYPE]
        hass.bus.async_fire(event_type, data[ATTR_EVENT_DATA],
                            EventOrigin.remote,
                            context=device_context(device))
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_RENDER_TEMPLATE:
        try:
            tpl = template.Template(data[ATTR_TEMPLATE], hass)
            rendered = tpl.async_render(data.get(ATTR_TEMPLATE_VARIABLES))
            return json_response({"rendered": rendered}, headers=headers)
        except (ValueError, TemplateError) as ex:
            return json_response(({"error": ex}), status=HTTP_BAD_REQUEST,
                                 headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_LOCATION:
        await hass.services.async_call(DT_DOMAIN,
                                       DT_SEE, data,
                                       blocking=True,
                                       context=device_context(device))
        return empty_okay_response(headers=headers)

    if webhook_type == WEBHOOK_TYPE_UPDATE_REGISTRATION:
        data[ATTR_APP_ID] = device[ATTR_APP_ID]
        data[ATTR_APP_NAME] = device[ATTR_APP_NAME]
        data[ATTR_SUPPORTS_ENCRYPTION] = device[ATTR_SUPPORTS_ENCRYPTION]
        data[CONF_SECRET] = device[CONF_SECRET]
        data[CONF_USER_ID] = device[CONF_USER_ID]
        data[CONF_WEBHOOK_ID] = device[CONF_WEBHOOK_ID]

        hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id] = data

        try:
            await store.async_save(savable_state(hass))
        except HomeAssistantError as ex:
            _LOGGER.error("Error updating mobile_app registration: %s", ex)
            return empty_okay_response()

        return json_response(safe_device(data))
