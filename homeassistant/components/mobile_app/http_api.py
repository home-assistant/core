"""Provides an HTTP API for mobile_app."""
import secrets
from typing import Dict

from aiohttp.web import Request, Response
from nacl.secret import SecretBox
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import CONF_WEBHOOK_ID, HTTP_CREATED
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_APP_VERSION,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_NAME,
    ATTR_OS_VERSION,
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_CLOUDHOOK_URL,
    CONF_REMOTE_UI_URL,
    CONF_SECRET,
    CONF_USER_ID,
    DOMAIN,
)
from .helpers import supports_encryption


class RegistrationsView(HomeAssistantView):
    """A view that accepts registration requests."""

    url = "/api/mobile_app/registrations"
    name = "api:mobile_app:register"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Optional(ATTR_APP_DATA, default={}): dict,
                vol.Required(ATTR_APP_ID): cv.string,
                vol.Required(ATTR_APP_NAME): cv.string,
                vol.Required(ATTR_APP_VERSION): cv.string,
                vol.Required(ATTR_DEVICE_NAME): cv.string,
                vol.Required(ATTR_MANUFACTURER): cv.string,
                vol.Required(ATTR_MODEL): cv.string,
                vol.Optional(ATTR_DEVICE_ID): cv.string,  # Added in 0.104
                vol.Required(ATTR_OS_NAME): cv.string,
                vol.Optional(ATTR_OS_VERSION): cv.string,
                vol.Required(ATTR_SUPPORTS_ENCRYPTION, default=False): cv.boolean,
            },
            # To allow future apps to send more data
            extra=vol.REMOVE_EXTRA,
        )
    )
    async def post(self, request: Request, data: Dict) -> Response:
        """Handle the POST request for registration."""
        hass = request.app["hass"]

        webhook_id = secrets.token_hex()

        if hass.components.cloud.async_active_subscription():
            data[
                CONF_CLOUDHOOK_URL
            ] = await hass.components.cloud.async_create_cloudhook(webhook_id)

        data[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] and supports_encryption():
            data[CONF_SECRET] = secrets.token_hex(SecretBox.KEY_SIZE)

        data[CONF_USER_ID] = request["hass_user"].id

        await hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=data, context={"source": "registration"}
            )
        )

        remote_ui_url = None
        try:
            remote_ui_url = hass.components.cloud.async_remote_ui_url()
        except hass.components.cloud.CloudNotAvailable:
            pass

        return self.json(
            {
                CONF_CLOUDHOOK_URL: data.get(CONF_CLOUDHOOK_URL),
                CONF_REMOTE_UI_URL: remote_ui_url,
                CONF_SECRET: data.get(CONF_SECRET),
                CONF_WEBHOOK_ID: data[CONF_WEBHOOK_ID],
            },
            status_code=HTTP_CREATED,
        )
