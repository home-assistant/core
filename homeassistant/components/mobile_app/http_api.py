"""Provides an HTTP API for mobile_app."""

from __future__ import annotations

from contextlib import suppress
from http import HTTPStatus
import secrets

from aiohttp.web import Request, Response
from nacl.secret import SecretBox
import voluptuous as vol

from homeassistant.components import cloud
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_APP_VERSION,
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
    SCHEMA_APP_DATA,
)
from .util import async_create_cloud_hook


class RegistrationsView(HomeAssistantView):
    """A view that accepts registration requests."""

    url = "/api/mobile_app/registrations"
    name = "api:mobile_app:register"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Optional(ATTR_APP_DATA, default={}): SCHEMA_APP_DATA,
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
    async def post(self, request: Request, data: dict) -> Response:
        """Handle the POST request for registration."""
        hass = request.app[KEY_HASS]

        webhook_id = secrets.token_hex()

        if cloud.async_active_subscription(hass):
            data[CONF_CLOUDHOOK_URL] = await async_create_cloud_hook(
                hass, webhook_id, None
            )

        data[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION]:
            data[CONF_SECRET] = secrets.token_hex(SecretBox.KEY_SIZE)

        data[CONF_USER_ID] = request["hass_user"].id

        # Fallback to DEVICE_ID if slug is empty.
        if not slugify(data[ATTR_DEVICE_NAME], separator=""):
            data[ATTR_DEVICE_NAME] = data[ATTR_DEVICE_ID]

        await hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=data, context={"source": "registration"}
            )
        )

        remote_ui_url = None
        if cloud.async_active_subscription(hass):
            with suppress(cloud.CloudNotAvailable):
                remote_ui_url = cloud.async_remote_ui_url(hass)

        return self.json(
            {
                CONF_CLOUDHOOK_URL: data.get(CONF_CLOUDHOOK_URL),
                CONF_REMOTE_UI_URL: remote_ui_url,
                CONF_SECRET: data.get(CONF_SECRET),
                CONF_WEBHOOK_ID: data[CONF_WEBHOOK_ID],
            },
            status_code=HTTPStatus.CREATED,
        )
