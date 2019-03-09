"""Provides an HTTP API for mobile_app."""
from typing import Dict

from aiohttp.web import Response, Request

from homeassistant.auth.util import generate_secret
from homeassistant.components.cloud import async_create_cloudhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import (HTTP_BAD_REQUEST, HTTP_CREATED,
                                 HTTP_INTERNAL_SERVER_ERROR, CONF_WEBHOOK_ID)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import get_component

from .const import (ATTR_APP_COMPONENT, ATTR_SUPPORTS_ENCRYPTION,
                    CONF_CLOUDHOOK_URL, CONF_SECRET, CONF_USER_ID,
                    DATA_REGISTRATIONS, DOMAIN, REGISTRATION_SCHEMA)

from .helpers import supports_encryption, savable_state

from .webhook import setup_registration


def register_http_handlers(hass: HomeAssistantType, store: Store) -> bool:
    """Register the HTTP handlers/views."""
    hass.http.register_view(RegistrationsView(store))
    return True


class RegistrationsView(HomeAssistantView):
    """A view that accepts registration requests."""

    url = '/api/mobile_app/registrations'
    name = 'api:mobile_app:register'

    def __init__(self, store: Store) -> None:
        """Initialize the view."""
        self._store = store

    @RequestDataValidator(REGISTRATION_SCHEMA)
    async def post(self, request: Request, data: Dict) -> Response:
        """Handle the POST request for registration."""
        hass = request.app['hass']

        if (ATTR_APP_COMPONENT in data and
                get_component(hass, data[ATTR_APP_COMPONENT]) is None):
            msg = "{} is not a component".format(data[ATTR_APP_COMPONENT])
            return self.json_message(msg, HTTP_BAD_REQUEST)

        webhook_id = generate_secret()

        if "cloud" in hass.config.components:
            cloudhook = await async_create_cloudhook(hass, webhook_id)

            if cloudhook is not None:
                data[CONF_CLOUDHOOK_URL] = cloudhook[CONF_CLOUDHOOK_URL]

        data[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] and supports_encryption():
            secret = generate_secret(16)

            data[CONF_SECRET] = secret

        data[CONF_USER_ID] = request['hass_user'].id

        hass.data[DOMAIN][DATA_REGISTRATIONS][webhook_id] = data

        try:
            await self._store.async_save(savable_state(hass))
        except HomeAssistantError:
            return self.json_message("Error saving registration.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        setup_registration(hass, self._store, data)

        return self.json({
            CONF_CLOUDHOOK_URL: data.get(CONF_CLOUDHOOK_URL),
            CONF_SECRET: data.get(CONF_SECRET),
            CONF_WEBHOOK_ID: data[CONF_WEBHOOK_ID],
        }, status_code=HTTP_CREATED)
