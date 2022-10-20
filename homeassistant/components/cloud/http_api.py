"""The HTTP api to control the cloud integration."""
import asyncio
import dataclasses
from functools import wraps
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import async_timeout
import attr
from hass_nabucasa import Cloud, auth, cloud_api, thingtalk
from hass_nabucasa.const import STATE_DISCONNECTED
from hass_nabucasa.voice import MAP_VOICE
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.alexa import (
    entities as alexa_entities,
    errors as alexa_errors,
)
from homeassistant.components.google_assistant import helpers as google_helpers
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.location import async_detect_location_info

from .const import (
    DOMAIN,
    PREF_ALEXA_DEFAULT_EXPOSE,
    PREF_ALEXA_REPORT_STATE,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_GOOGLE,
    PREF_GOOGLE_DEFAULT_EXPOSE,
    PREF_GOOGLE_REPORT_STATE,
    PREF_GOOGLE_SECURE_DEVICES_PIN,
    PREF_TTS_DEFAULT_VOICE,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


_CLOUD_ERRORS = {
    asyncio.TimeoutError: (
        HTTPStatus.BAD_GATEWAY,
        "Unable to reach the Home Assistant cloud.",
    ),
    aiohttp.ClientError: (
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "Error making internal request",
    ),
}


async def async_setup(hass):
    """Initialize the HTTP API."""
    websocket_api.async_register_command(hass, websocket_cloud_status)
    websocket_api.async_register_command(hass, websocket_subscription)
    websocket_api.async_register_command(hass, websocket_update_prefs)
    websocket_api.async_register_command(hass, websocket_hook_create)
    websocket_api.async_register_command(hass, websocket_hook_delete)
    websocket_api.async_register_command(hass, websocket_remote_connect)
    websocket_api.async_register_command(hass, websocket_remote_disconnect)

    websocket_api.async_register_command(hass, google_assistant_list)
    websocket_api.async_register_command(hass, google_assistant_update)

    websocket_api.async_register_command(hass, alexa_list)
    websocket_api.async_register_command(hass, alexa_update)
    websocket_api.async_register_command(hass, alexa_sync)

    websocket_api.async_register_command(hass, thingtalk_convert)
    websocket_api.async_register_command(hass, tts_info)

    hass.http.register_view(GoogleActionsSyncView)
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudRegisterView)
    hass.http.register_view(CloudResendConfirmView)
    hass.http.register_view(CloudForgotPasswordView)

    _CLOUD_ERRORS.update(
        {
            auth.UserNotFound: (HTTPStatus.BAD_REQUEST, "User does not exist."),
            auth.UserNotConfirmed: (HTTPStatus.BAD_REQUEST, "Email not confirmed."),
            auth.UserExists: (
                HTTPStatus.BAD_REQUEST,
                "An account with the given email already exists.",
            ),
            auth.Unauthenticated: (HTTPStatus.UNAUTHORIZED, "Authentication failed."),
            auth.PasswordChangeRequired: (
                HTTPStatus.BAD_REQUEST,
                "Password change required.",
            ),
        }
    )


def _handle_cloud_errors(handler):
    """Webview decorator to handle auth errors."""

    @wraps(handler)
    async def error_handler(view, request, *args, **kwargs):
        """Handle exceptions that raise from the wrapped request handler."""
        try:
            result = await handler(view, request, *args, **kwargs)
            return result

        except Exception as err:  # pylint: disable=broad-except
            status, msg = _process_cloud_exception(err, request.path)
            return view.json_message(
                msg, status_code=status, message_code=err.__class__.__name__.lower()
            )

    return error_handler


def _ws_handle_cloud_errors(handler):
    """Websocket decorator to handle auth errors."""

    @wraps(handler)
    async def error_handler(hass, connection, msg):
        """Handle exceptions that raise from the wrapped handler."""
        try:
            return await handler(hass, connection, msg)

        except Exception as err:  # pylint: disable=broad-except
            err_status, err_msg = _process_cloud_exception(err, msg["type"])
            connection.send_error(msg["id"], err_status, err_msg)

    return error_handler


def _process_cloud_exception(exc, where):
    """Process a cloud exception."""
    err_info = None

    for err, value_info in _CLOUD_ERRORS.items():
        if isinstance(exc, err):
            err_info = value_info
            break

    if err_info is None:
        _LOGGER.exception("Unexpected error processing request for %s", where)
        err_info = (HTTPStatus.BAD_GATEWAY, f"Unexpected error: {exc}")

    return err_info


class GoogleActionsSyncView(HomeAssistantView):
    """Trigger a Google Actions Smart Home Sync."""

    url = "/api/cloud/google_actions/sync"
    name = "api:cloud:google_actions/sync"

    @_handle_cloud_errors
    async def post(self, request):
        """Trigger a Google Actions sync."""
        hass = request.app["hass"]
        cloud: Cloud = hass.data[DOMAIN]
        gconf = await cloud.client.get_google_config()
        status = await gconf.async_sync_entities(gconf.agent_user_id)
        return self.json({}, status_code=status)


class CloudLoginView(HomeAssistantView):
    """Login to Home Assistant cloud."""

    url = "/api/cloud/login"
    name = "api:cloud:login"

    @_handle_cloud_errors
    @RequestDataValidator(
        vol.Schema({vol.Required("email"): str, vol.Required("password"): str})
    )
    async def post(self, request, data):
        """Handle login request."""
        hass = request.app["hass"]
        cloud = hass.data[DOMAIN]
        await cloud.login(data["email"], data["password"])

        return self.json({"success": True})


class CloudLogoutView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = "/api/cloud/logout"
    name = "api:cloud:logout"

    @_handle_cloud_errors
    async def post(self, request):
        """Handle logout request."""
        hass = request.app["hass"]
        cloud = hass.data[DOMAIN]

        async with async_timeout.timeout(REQUEST_TIMEOUT):
            await cloud.logout()

        return self.json_message("ok")


class CloudRegisterView(HomeAssistantView):
    """Register on the Home Assistant cloud."""

    url = "/api/cloud/register"
    name = "api:cloud:register"

    @_handle_cloud_errors
    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): vol.All(str, vol.Length(min=6)),
            }
        )
    )
    async def post(self, request, data):
        """Handle registration request."""
        hass = request.app["hass"]
        cloud = hass.data[DOMAIN]

        client_metadata = None

        if location_info := await async_detect_location_info(
            async_get_clientsession(hass)
        ):
            client_metadata = {
                "NC_COUNTRY_CODE": location_info.country_code,
                "NC_REGION_CODE": location_info.region_code,
                "NC_ZIP_CODE": location_info.zip_code,
            }

        async with async_timeout.timeout(REQUEST_TIMEOUT):
            await cloud.auth.async_register(
                data["email"],
                data["password"],
                client_metadata=client_metadata,
            )

        return self.json_message("ok")


class CloudResendConfirmView(HomeAssistantView):
    """Resend email confirmation code."""

    url = "/api/cloud/resend_confirm"
    name = "api:cloud:resend_confirm"

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({vol.Required("email"): str}))
    async def post(self, request, data):
        """Handle resending confirm email code request."""
        hass = request.app["hass"]
        cloud = hass.data[DOMAIN]

        async with async_timeout.timeout(REQUEST_TIMEOUT):
            await cloud.auth.async_resend_email_confirm(data["email"])

        return self.json_message("ok")


class CloudForgotPasswordView(HomeAssistantView):
    """View to start Forgot Password flow.."""

    url = "/api/cloud/forgot_password"
    name = "api:cloud:forgot_password"

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({vol.Required("email"): str}))
    async def post(self, request, data):
        """Handle forgot password request."""
        hass = request.app["hass"]
        cloud = hass.data[DOMAIN]

        async with async_timeout.timeout(REQUEST_TIMEOUT):
            await cloud.auth.async_forgot_password(data["email"])

        return self.json_message("ok")


@websocket_api.websocket_command({vol.Required("type"): "cloud/status"})
@websocket_api.async_response
async def websocket_cloud_status(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info.

    Async friendly.
    """
    cloud = hass.data[DOMAIN]
    connection.send_message(
        websocket_api.result_message(msg["id"], await _account_data(hass, cloud))
    )


def _require_cloud_login(handler):
    """Websocket decorator that requires cloud to be logged in."""

    @wraps(handler)
    def with_cloud_auth(hass, connection, msg):
        """Require to be logged into the cloud."""
        cloud = hass.data[DOMAIN]
        if not cloud.is_logged_in:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"], "not_logged_in", "You need to be logged in to the cloud."
                )
            )
            return

        handler(hass, connection, msg)

    return with_cloud_auth


@_require_cloud_login
@websocket_api.websocket_command({vol.Required("type"): "cloud/subscription"})
@websocket_api.async_response
async def websocket_subscription(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    try:
        async with async_timeout.timeout(REQUEST_TIMEOUT):
            data = await cloud_api.async_subscription_info(cloud)
    except aiohttp.ClientError:
        connection.send_error(
            msg["id"], "request_failed", "Failed to request subscription"
        )
    else:
        connection.send_result(msg["id"], data)


@_require_cloud_login
@websocket_api.websocket_command(
    {
        vol.Required("type"): "cloud/update_prefs",
        vol.Optional(PREF_ENABLE_GOOGLE): bool,
        vol.Optional(PREF_ENABLE_ALEXA): bool,
        vol.Optional(PREF_ALEXA_REPORT_STATE): bool,
        vol.Optional(PREF_GOOGLE_REPORT_STATE): bool,
        vol.Optional(PREF_ALEXA_DEFAULT_EXPOSE): [str],
        vol.Optional(PREF_GOOGLE_DEFAULT_EXPOSE): [str],
        vol.Optional(PREF_GOOGLE_SECURE_DEVICES_PIN): vol.Any(None, str),
        vol.Optional(PREF_TTS_DEFAULT_VOICE): vol.All(
            vol.Coerce(tuple), vol.In(MAP_VOICE)
        ),
    }
)
@websocket_api.async_response
async def websocket_update_prefs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]

    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")

    # If we turn alexa linking on, validate that we can fetch access token
    if changes.get(PREF_ALEXA_REPORT_STATE):
        alexa_config = await cloud.client.get_alexa_config()
        try:
            async with async_timeout.timeout(10):
                await alexa_config.async_get_access_token()
        except asyncio.TimeoutError:
            connection.send_error(
                msg["id"], "alexa_timeout", "Timeout validating Alexa access token."
            )
            return
        except (alexa_errors.NoTokenAvailable, alexa_errors.RequireRelink):
            connection.send_error(
                msg["id"],
                "alexa_relink",
                "Please go to the Alexa app and re-link the Home Assistant "
                "skill and then try to enable state reporting.",
            )
            await alexa_config.set_authorized(False)
            return

        await alexa_config.set_authorized(True)

    await cloud.client.prefs.async_update(**changes)

    connection.send_message(websocket_api.result_message(msg["id"]))


@_require_cloud_login
@websocket_api.websocket_command(
    {
        vol.Required("type"): "cloud/cloudhook/create",
        vol.Required("webhook_id"): str,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_hook_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    hook = await cloud.cloudhooks.async_create(msg["webhook_id"], False)
    connection.send_message(websocket_api.result_message(msg["id"], hook))


@_require_cloud_login
@websocket_api.websocket_command(
    {
        vol.Required("type"): "cloud/cloudhook/delete",
        vol.Required("webhook_id"): str,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_hook_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    await cloud.cloudhooks.async_delete(msg["webhook_id"])
    connection.send_message(websocket_api.result_message(msg["id"]))


async def _account_data(hass: HomeAssistant, cloud: Cloud):
    """Generate the auth data JSON response."""

    assert hass.config.api
    if not cloud.is_logged_in:
        return {
            "logged_in": False,
            "cloud": STATE_DISCONNECTED,
            "http_use_ssl": hass.config.api.use_ssl,
        }

    claims = cloud.claims
    client = cloud.client
    remote = cloud.remote

    alexa_config = await client.get_alexa_config()
    google_config = await client.get_google_config()

    # Load remote certificate
    if remote.certificate:
        certificate = attr.asdict(remote.certificate)
    else:
        certificate = None

    if cloud.iot.last_disconnect_reason:
        cloud_last_disconnect_reason = dataclasses.asdict(
            cloud.iot.last_disconnect_reason
        )
    else:
        cloud_last_disconnect_reason = None

    return {
        "alexa_entities": client.alexa_user_config["filter"].config,
        "alexa_registered": alexa_config.authorized,
        "cloud": cloud.iot.state,
        "cloud_last_disconnect_reason": cloud_last_disconnect_reason,
        "email": claims["email"],
        "google_entities": client.google_user_config["filter"].config,
        "google_registered": google_config.has_registered_user_agent,
        "google_local_connected": google_config.is_local_connected,
        "logged_in": True,
        "prefs": client.prefs.as_dict(),
        "remote_certificate": certificate,
        "remote_connected": remote.is_connected,
        "remote_domain": remote.instance_domain,
        "http_use_ssl": hass.config.api.use_ssl,
        "active_subscription": not cloud.subscription_expired,
    }


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command({"type": "cloud/remote/connect"})
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_remote_connect(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for connect remote."""
    cloud = hass.data[DOMAIN]
    await cloud.client.prefs.async_update(remote_enabled=True)
    connection.send_result(msg["id"], await _account_data(hass, cloud))


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command({"type": "cloud/remote/disconnect"})
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_remote_disconnect(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for disconnect remote."""
    cloud = hass.data[DOMAIN]
    await cloud.client.prefs.async_update(remote_enabled=False)
    connection.send_result(msg["id"], await _account_data(hass, cloud))


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command({"type": "cloud/google_assistant/entities"})
@websocket_api.async_response
@_ws_handle_cloud_errors
async def google_assistant_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all google assistant entities."""
    cloud = hass.data[DOMAIN]
    gconf = await cloud.client.get_google_config()
    entities = google_helpers.async_get_entities(hass, gconf)

    result = []

    for entity in entities:
        result.append(
            {
                "entity_id": entity.entity_id,
                "traits": [trait.name for trait in entity.traits()],
                "might_2fa": entity.might_2fa_traits(),
            }
        )

    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command(
    {
        "type": "cloud/google_assistant/entities/update",
        "entity_id": str,
        vol.Optional("should_expose"): vol.Any(None, bool),
        vol.Optional("override_name"): str,
        vol.Optional("aliases"): [str],
        vol.Optional("disable_2fa"): bool,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def google_assistant_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update google assistant config."""
    cloud = hass.data[DOMAIN]
    changes = dict(msg)
    changes.pop("type")
    changes.pop("id")

    await cloud.client.prefs.async_update_google_entity_config(**changes)

    connection.send_result(
        msg["id"], cloud.client.prefs.google_entity_configs.get(msg["entity_id"])
    )


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command({"type": "cloud/alexa/entities"})
@websocket_api.async_response
@_ws_handle_cloud_errors
async def alexa_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all alexa entities."""
    cloud = hass.data[DOMAIN]
    alexa_config = await cloud.client.get_alexa_config()
    entities = alexa_entities.async_get_entities(hass, alexa_config)

    result = []

    for entity in entities:
        result.append(
            {
                "entity_id": entity.entity_id,
                "display_categories": entity.default_display_categories(),
                "interfaces": [ifc.name() for ifc in entity.interfaces()],
            }
        )

    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command(
    {
        "type": "cloud/alexa/entities/update",
        "entity_id": str,
        vol.Optional("should_expose"): vol.Any(None, bool),
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def alexa_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update alexa entity config."""
    cloud = hass.data[DOMAIN]
    changes = dict(msg)
    changes.pop("type")
    changes.pop("id")

    await cloud.client.prefs.async_update_alexa_entity_config(**changes)

    connection.send_result(
        msg["id"], cloud.client.prefs.alexa_entity_configs.get(msg["entity_id"])
    )


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command({"type": "cloud/alexa/sync"})
@websocket_api.async_response
async def alexa_sync(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Sync with Alexa."""
    cloud = hass.data[DOMAIN]
    alexa_config = await cloud.client.get_alexa_config()

    async with async_timeout.timeout(10):
        try:
            success = await alexa_config.async_sync_entities()
        except alexa_errors.NoTokenAvailable:
            connection.send_error(
                msg["id"],
                "alexa_relink",
                "Please go to the Alexa app and re-link the Home Assistant skill.",
            )
            return

    if success:
        connection.send_result(msg["id"])
    else:
        connection.send_error(
            msg["id"], websocket_api.ERR_UNKNOWN_ERROR, "Unknown error"
        )


@websocket_api.websocket_command({"type": "cloud/thingtalk/convert", "query": str})
@websocket_api.async_response
async def thingtalk_convert(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Convert a query."""
    cloud = hass.data[DOMAIN]

    async with async_timeout.timeout(10):
        try:
            connection.send_result(
                msg["id"], await thingtalk.async_convert(cloud, msg["query"])
            )
        except thingtalk.ThingTalkConversionError as err:
            connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))


@websocket_api.websocket_command({"type": "cloud/tts/info"})
def tts_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Fetch available tts info."""
    connection.send_result(
        msg["id"], {"languages": [(lang, gender.value) for lang, gender in MAP_VOICE]}
    )
