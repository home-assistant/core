"""Provides an HTTP API for mobile_app."""
from aiohttp.web import Request

from homeassistant.auth.util import generate_secret
from homeassistant.components.cloud import async_create_cloudhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import (HTTP_CREATED, HTTP_INTERNAL_SERVER_ERROR,
                                 CONF_WEBHOOK_ID)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_REGISTRATIONS, ATTR_SUPPORTS_ENCRYPTION,
                    CONF_CLOUDHOOK_ID, CONF_CLOUDHOOK_URL, CONF_SECRET,
                    CONF_USER_ID, DOMAIN, REGISTER_DEVICE_SCHEMA)

from .helpers import supports_encryption, savable_state

from .webhook import register_device_webhook


def register_http_handlers(hass: HomeAssistantType, store: Store):
    """Register the HTTP handlers/views."""
    hass.http.register_view(DevicesView(store))
    return True


class DevicesView(HomeAssistantView):
    """A view that accepts device registration requests."""

    url = '/api/mobile_app/devices'
    name = 'api:mobile_app:register-device'

    def __init__(self, store: Store):
        """Initialize the view."""
        self._store = store

    @RequestDataValidator(REGISTER_DEVICE_SCHEMA)
    async def post(self, request: Request, data: dict):
        """Handle the POST request for device registration."""
        hass = request.app['hass']

        resp = {}

        webhook_id = generate_secret()

        cloudhook = await async_create_cloudhook(hass, webhook_id)

        if cloudhook is not None:
            data[CONF_CLOUDHOOK_ID] = resp[CONF_CLOUDHOOK_ID] = \
                cloudhook[CONF_CLOUDHOOK_ID]
            data[CONF_CLOUDHOOK_URL] = resp[CONF_CLOUDHOOK_URL] = \
                cloudhook[CONF_CLOUDHOOK_URL]

        data[CONF_WEBHOOK_ID] = resp[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] and supports_encryption():
            secret = generate_secret(16)

            data[CONF_SECRET] = resp[CONF_SECRET] = secret

        data[CONF_USER_ID] = request['hass_user'].id

        hass.data[DOMAIN][ATTR_REGISTRATIONS][webhook_id] = data

        try:
            await self._store.async_save(savable_state(hass))
        except HomeAssistantError:
            return self.json_message("Error saving device.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        register_device_webhook(hass, self._store, data)

        return self.json(resp, status_code=HTTP_CREATED)
