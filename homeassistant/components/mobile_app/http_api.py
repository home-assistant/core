"""Provides an HTTP API for mobile_app."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import asyncio
from contextlib import suppress
from http import HTTPStatus
import secrets

from aiohttp.web import Request, Response
from nacl.secret import SecretBox
import probatio

from homeassistant.auth.models import User
from homeassistant.components import cloud
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
    DATA_REGISTRATION_LOCK,
    DOMAIN,
    SCHEMA_APP_DATA,
)
from .util import (
    async_create_cloud_hook,
    async_delete_registration_cloudhook,
    async_update_registration,
)


class RegistrationsView(HomeAssistantView):
    """A view that accepts registration requests."""

    url = "/api/mobile_app/registrations"
    name = "api:mobile_app:register"

    @RequestDataValidator(
        probatio.Schema(
            {
                probatio.Optional(ATTR_APP_DATA, default={}): SCHEMA_APP_DATA,
                probatio.Required(ATTR_APP_ID): cv.string,
                probatio.Required(ATTR_APP_NAME): cv.string,
                probatio.Required(ATTR_APP_VERSION): cv.string,
                probatio.Required(ATTR_DEVICE_NAME): cv.string,
                probatio.Required(ATTR_MANUFACTURER): cv.string,
                probatio.Required(ATTR_MODEL): cv.string,
                probatio.Optional(ATTR_DEVICE_ID): cv.string,  # Added in 0.104
                probatio.Required(ATTR_OS_NAME): cv.string,
                probatio.Optional(ATTR_OS_VERSION): cv.string,
                probatio.Required(ATTR_SUPPORTS_ENCRYPTION, default=False): cv.boolean,
            },
            # To allow future apps to send more data
            extra=probatio.REMOVE_EXTRA,
        )
    )
    async def post(self, request: Request, data: dict) -> Response:
        """Handle the POST request for registration."""
        hass = request.app[KEY_HASS]
        user = request["hass_user"]

        # Shield so the registration is completed or rolled back, even if the
        # app hangs up
        registered = await asyncio.shield(
            hass.async_create_task(
                _async_register(hass, user, data),
                "mobile_app registration",
                eager_start=True,
            )
        )
        if not registered:
            return self.json_message(
                "Failed to register the app", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        remote_ui_url = None
        if not user.local_only and cloud.async_active_subscription(hass):
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


async def _async_register(hass: HomeAssistant, user: User, data: dict) -> bool:
    """Register an app, return True if successful."""
    # Serialize registrations, an app registering again updates its entry
    async with hass.data[DOMAIN][DATA_REGISTRATION_LOCK]:
        return await _async_register_locked(hass, user, data)


async def _async_register_locked(hass: HomeAssistant, user: User, data: dict) -> bool:
    """Register an app while holding the registration lock."""
    webhook_id = secrets.token_hex()

    if (
        not user.local_only
        and cloud.async_active_subscription(hass)
        and cloud.async_is_connected(hass)
    ):
        data[CONF_CLOUDHOOK_URL] = await async_create_cloud_hook(hass, webhook_id, None)

    data[CONF_WEBHOOK_ID] = webhook_id

    if data[ATTR_SUPPORTS_ENCRYPTION]:
        data[CONF_SECRET] = secrets.token_hex(SecretBox.KEY_SIZE)

    data[CONF_USER_ID] = user.id

    # Fallback to DEVICE_ID if slug is empty.
    if not slugify(data[ATTR_DEVICE_NAME], separator=""):
        data[ATTR_DEVICE_NAME] = data[ATTR_DEVICE_ID]

    if ATTR_DEVICE_ID in data and (
        entry := hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, f"{data[ATTR_APP_ID]}-{data[ATTR_DEVICE_ID]}"
        )
    ):
        return await async_update_registration(hass, entry, data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=data, context={"source": "registration"}
    )
    if result["type"] is FlowResultType.CREATE_ENTRY:
        return True
    await async_delete_registration_cloudhook(hass, data)
    return False
