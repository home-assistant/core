"""The HTTP api to control the cloud integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from contextlib import suppress
import dataclasses
from functools import wraps
from http import HTTPStatus
import logging
import time
from typing import Any, Concatenate

import aiohttp
from aiohttp import web
import attr
from hass_nabucasa import Cloud, auth, thingtalk
from hass_nabucasa.const import STATE_DISCONNECTED
from hass_nabucasa.voice import TTS_VOICES
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.alexa import (
    entities as alexa_entities,
    errors as alexa_errors,
)
from homeassistant.components.google_assistant import helpers as google_helpers
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.location import async_detect_location_info

from .alexa_config import entity_supported as entity_supported_by_alexa
from .assist_pipeline import async_create_cloud_pipeline
from .client import CloudClient
from .const import (
    DATA_CLOUD,
    EVENT_CLOUD_EVENT,
    LOGIN_MFA_TIMEOUT,
    PREF_ALEXA_REPORT_STATE,
    PREF_DISABLE_2FA,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_CLOUD_ICE_SERVERS,
    PREF_ENABLE_GOOGLE,
    PREF_GOOGLE_REPORT_STATE,
    PREF_GOOGLE_SECURE_DEVICES_PIN,
    PREF_REMOTE_ALLOW_REMOTE_ENABLE,
    PREF_TTS_DEFAULT_VOICE,
    REQUEST_TIMEOUT,
)
from .google_config import CLOUD_GOOGLE
from .repairs import async_manage_legacy_subscription_issue
from .subscription import async_subscription_info

_LOGGER = logging.getLogger(__name__)


_CLOUD_ERRORS: dict[type[Exception], tuple[HTTPStatus, str]] = {
    TimeoutError: (
        HTTPStatus.BAD_GATEWAY,
        "Unable to reach the Home Assistant cloud.",
    ),
    aiohttp.ClientError: (
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "Error making internal request",
    ),
}


class MFAExpiredOrNotStarted(auth.CloudError):
    """Multi-factor authentication expired, or not started."""


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Initialize the HTTP API."""
    websocket_api.async_register_command(hass, websocket_cloud_remove_data)
    websocket_api.async_register_command(hass, websocket_cloud_status)
    websocket_api.async_register_command(hass, websocket_subscription)
    websocket_api.async_register_command(hass, websocket_update_prefs)
    websocket_api.async_register_command(hass, websocket_hook_create)
    websocket_api.async_register_command(hass, websocket_hook_delete)
    websocket_api.async_register_command(hass, websocket_remote_connect)
    websocket_api.async_register_command(hass, websocket_remote_disconnect)

    websocket_api.async_register_command(hass, google_assistant_get)
    websocket_api.async_register_command(hass, google_assistant_list)
    websocket_api.async_register_command(hass, google_assistant_update)

    websocket_api.async_register_command(hass, alexa_get)
    websocket_api.async_register_command(hass, alexa_list)
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
            auth.InvalidTotpCode: (HTTPStatus.BAD_REQUEST, "Invalid TOTP code."),
            auth.MFARequired: (
                HTTPStatus.UNAUTHORIZED,
                "Multi-factor authentication required.",
            ),
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
            MFAExpiredOrNotStarted: (
                HTTPStatus.BAD_REQUEST,
                "Multi-factor authentication expired, or not started. Please try again.",
            ),
        }
    )


def _handle_cloud_errors[_HassViewT: HomeAssistantView, **_P](
    handler: Callable[
        Concatenate[_HassViewT, web.Request, _P], Awaitable[web.Response]
    ],
) -> Callable[
    Concatenate[_HassViewT, web.Request, _P], Coroutine[Any, Any, web.Response]
]:
    """Webview decorator to handle auth errors."""

    @wraps(handler)
    async def error_handler(
        view: _HassViewT, request: web.Request, *args: _P.args, **kwargs: _P.kwargs
    ) -> web.Response:
        """Handle exceptions that raise from the wrapped request handler."""
        try:
            result = await handler(view, request, *args, **kwargs)
        except Exception as err:  # noqa: BLE001
            status, msg = _process_cloud_exception(err, request.path)
            return view.json_message(
                msg, status_code=status, message_code=err.__class__.__name__.lower()
            )
        return result

    return error_handler


def _ws_handle_cloud_errors(
    handler: Callable[
        [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]],
        Coroutine[None, None, None],
    ],
) -> Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]],
    Coroutine[None, None, None],
]:
    """Websocket decorator to handle auth errors."""

    @wraps(handler)
    async def error_handler(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Handle exceptions that raise from the wrapped handler."""
        try:
            return await handler(hass, connection, msg)

        except Exception as err:  # noqa: BLE001
            err_status, err_msg = _process_cloud_exception(err, msg["type"])
            connection.send_error(msg["id"], str(err_status), err_msg)

    return error_handler


def _process_cloud_exception(exc: Exception, where: str) -> tuple[HTTPStatus, str]:
    """Process a cloud exception."""
    err_info: tuple[HTTPStatus, str] | None = None

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

    @require_admin
    @_handle_cloud_errors
    async def post(self, request: web.Request) -> web.Response:
        """Trigger a Google Actions sync."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]
        gconf = await cloud.client.get_google_config()
        status = await gconf.async_sync_entities(gconf.agent_user_id)
        return self.json({}, status_code=status)


class CloudLoginView(HomeAssistantView):
    """Login to Home Assistant cloud."""

    _mfa_tokens: dict[str, str] = {}
    _mfa_tokens_set_time: float = 0

    url = "/api/cloud/login"
    name = "api:cloud:login"

    @require_admin
    @_handle_cloud_errors
    @RequestDataValidator(
        vol.Schema(
            vol.All(
                {
                    vol.Required("email"): str,
                    vol.Exclusive("password", "login"): str,
                    vol.Exclusive("code", "login"): str,
                },
                cv.has_at_least_one_key("password", "code"),
            )
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle login request."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]

        try:
            email = data["email"]
            password = data.get("password")
            code = data.get("code")

            if email and password:
                await cloud.login(email, password)

            else:
                if (
                    not self._mfa_tokens
                    or time.time() - self._mfa_tokens_set_time > LOGIN_MFA_TIMEOUT
                ):
                    raise MFAExpiredOrNotStarted

                # Voluptuous should ensure that code is not None because password is
                assert code is not None

                await cloud.login_verify_totp(email, code, self._mfa_tokens)
                self._mfa_tokens = {}
                self._mfa_tokens_set_time = 0

        except auth.MFARequired as mfa_err:
            self._mfa_tokens = mfa_err.mfa_tokens
            self._mfa_tokens_set_time = time.time()
            raise

        if "assist_pipeline" in hass.config.components:
            new_cloud_pipeline_id = await async_create_cloud_pipeline(hass)
        else:
            new_cloud_pipeline_id = None

        async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": "login"})
        return self.json({"success": True, "cloud_pipeline": new_cloud_pipeline_id})


class CloudLogoutView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = "/api/cloud/logout"
    name = "api:cloud:logout"

    @require_admin
    @_handle_cloud_errors
    async def post(self, request: web.Request) -> web.Response:
        """Handle logout request."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]

        async with asyncio.timeout(REQUEST_TIMEOUT):
            await cloud.logout()

        async_dispatcher_send(hass, EVENT_CLOUD_EVENT, {"type": "logout"})
        return self.json_message("ok")


class CloudRegisterView(HomeAssistantView):
    """Register on the Home Assistant cloud."""

    url = "/api/cloud/register"
    name = "api:cloud:register"

    @require_admin
    @_handle_cloud_errors
    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): vol.All(str, vol.Length(min=6)),
            }
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle registration request."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]

        client_metadata = None

        if (
            location_info := await async_detect_location_info(
                async_get_clientsession(hass)
            )
        ) and location_info.country_code is not None:
            client_metadata = {"NC_COUNTRY_CODE": location_info.country_code}
            if location_info.region_code is not None:
                client_metadata["NC_REGION_CODE"] = location_info.region_code
            if location_info.zip_code is not None:
                client_metadata["NC_ZIP_CODE"] = location_info.zip_code

        async with asyncio.timeout(REQUEST_TIMEOUT):
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

    @require_admin
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({vol.Required("email"): str}))
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle resending confirm email code request."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]

        async with asyncio.timeout(REQUEST_TIMEOUT):
            await cloud.auth.async_resend_email_confirm(data["email"])

        return self.json_message("ok")


class CloudForgotPasswordView(HomeAssistantView):
    """View to start Forgot Password flow.."""

    url = "/api/cloud/forgot_password"
    name = "api:cloud:forgot_password"

    @require_admin
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({vol.Required("email"): str}))
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle forgot password request."""
        hass = request.app[KEY_HASS]
        cloud = hass.data[DATA_CLOUD]

        async with asyncio.timeout(REQUEST_TIMEOUT):
            await cloud.auth.async_forgot_password(data["email"])

        return self.json_message("ok")


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "cloud/remove_data"})
@websocket_api.async_response
async def websocket_cloud_remove_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for account info.

    Async friendly.
    """
    cloud = hass.data[DATA_CLOUD]
    if cloud.is_logged_in:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "logged_in", "Can't remove data when logged in."
            )
        )
        return

    await cloud.remove_data()
    await cloud.client.prefs.async_erase_config()

    connection.send_message(websocket_api.result_message(msg["id"]))


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
    cloud = hass.data[DATA_CLOUD]
    connection.send_message(
        websocket_api.result_message(msg["id"], await _account_data(hass, cloud))
    )


def _require_cloud_login(
    handler: Callable[
        [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]],
        None,
    ],
) -> Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]],
    None,
]:
    """Websocket decorator that requires cloud to be logged in."""

    @wraps(handler)
    def with_cloud_auth(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Require to be logged into the cloud."""
        cloud = hass.data[DATA_CLOUD]
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
    cloud = hass.data[DATA_CLOUD]
    if (data := await async_subscription_info(cloud)) is None:
        connection.send_error(
            msg["id"], "request_failed", "Failed to request subscription"
        )
        return

    connection.send_result(msg["id"], data)
    async_manage_legacy_subscription_issue(hass, data)


def validate_language_voice(value: tuple[str, str]) -> tuple[str, str]:
    """Validate language and voice."""
    language, voice = value
    if language not in TTS_VOICES:
        raise vol.Invalid(f"Invalid language {language}")
    if voice not in TTS_VOICES[language]:
        raise vol.Invalid(f"Invalid voice {voice} for language {language}")
    return value


@_require_cloud_login
@websocket_api.websocket_command(
    {
        vol.Required("type"): "cloud/update_prefs",
        vol.Optional(PREF_ALEXA_REPORT_STATE): bool,
        vol.Optional(PREF_ENABLE_ALEXA): bool,
        vol.Optional(PREF_ENABLE_CLOUD_ICE_SERVERS): bool,
        vol.Optional(PREF_ENABLE_GOOGLE): bool,
        vol.Optional(PREF_GOOGLE_REPORT_STATE): bool,
        vol.Optional(PREF_GOOGLE_SECURE_DEVICES_PIN): vol.Any(None, str),
        vol.Optional(PREF_REMOTE_ALLOW_REMOTE_ENABLE): bool,
        vol.Optional(PREF_TTS_DEFAULT_VOICE): vol.All(
            vol.Coerce(tuple), validate_language_voice
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
    cloud = hass.data[DATA_CLOUD]

    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")

    # If we turn alexa linking on, validate that we can fetch access token
    if changes.get(PREF_ALEXA_REPORT_STATE):
        alexa_config = await cloud.client.get_alexa_config()
        try:
            async with asyncio.timeout(10):
                await alexa_config.async_get_access_token()
        except TimeoutError:
            connection.send_error(
                msg["id"], "alexa_timeout", "Timeout validating Alexa access token."
            )
            return
        except (alexa_errors.NoTokenAvailable, alexa_errors.RequireRelink):
            connection.send_error(
                msg["id"],
                "alexa_relink",
                (
                    "Please go to the Alexa app and re-link the Home Assistant "
                    "skill and then try to enable state reporting."
                ),
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
    cloud = hass.data[DATA_CLOUD]
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
    cloud = hass.data[DATA_CLOUD]
    await cloud.cloudhooks.async_delete(msg["webhook_id"])
    connection.send_message(websocket_api.result_message(msg["id"]))


async def _account_data(
    hass: HomeAssistant, cloud: Cloud[CloudClient]
) -> dict[str, Any]:
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
        "remote_certificate_status": remote.certificate_status,
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
    cloud = hass.data[DATA_CLOUD]
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
    cloud = hass.data[DATA_CLOUD]
    await cloud.client.prefs.async_update(remote_enabled=False)
    connection.send_result(msg["id"], await _account_data(hass, cloud))


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command(
    {
        "type": "cloud/google_assistant/entities/get",
        "entity_id": str,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def google_assistant_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get data for a single google assistant entity."""
    cloud = hass.data[DATA_CLOUD]
    gconf = await cloud.client.get_google_config()
    entity_id: str = msg["entity_id"]
    state = hass.states.get(entity_id)

    if not state:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"{entity_id} unknown",
        )
        return

    entity = google_helpers.GoogleEntity(hass, gconf, state)
    if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES or not entity.is_supported():
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            f"{entity_id} not supported by Google assistant",
        )
        return

    assistant_options: Mapping[str, Any] = {}
    with suppress(HomeAssistantError, KeyError):
        settings = exposed_entities.async_get_entity_settings(hass, entity_id)
        assistant_options = settings[CLOUD_GOOGLE]

    result = {
        "entity_id": entity.entity_id,
        "traits": [trait.name for trait in entity.traits()],
        "might_2fa": entity.might_2fa_traits(),
        PREF_DISABLE_2FA: assistant_options.get(PREF_DISABLE_2FA),
    }

    connection.send_result(msg["id"], result)


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
    cloud = hass.data[DATA_CLOUD]
    gconf = await cloud.client.get_google_config()
    entities = google_helpers.async_get_entities(hass, gconf)

    result = [
        {
            "entity_id": entity.entity_id,
            "traits": [trait.name for trait in entity.traits()],
            "might_2fa": entity.might_2fa_traits(),
        }
        for entity in entities
    ]

    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command(
    {
        "type": "cloud/google_assistant/entities/update",
        "entity_id": str,
        vol.Optional(PREF_DISABLE_2FA): bool,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def google_assistant_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update google assistant entity config."""
    entity_id: str = msg["entity_id"]

    assistant_options: Mapping[str, Any] = {}
    with suppress(HomeAssistantError, KeyError):
        settings = exposed_entities.async_get_entity_settings(hass, entity_id)
        assistant_options = settings[CLOUD_GOOGLE]

    disable_2fa = msg[PREF_DISABLE_2FA]
    if assistant_options.get(PREF_DISABLE_2FA) == disable_2fa:
        return

    exposed_entities.async_set_assistant_option(
        hass, CLOUD_GOOGLE, entity_id, PREF_DISABLE_2FA, disable_2fa
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@_require_cloud_login
@websocket_api.websocket_command(
    {
        "type": "cloud/alexa/entities/get",
        "entity_id": str,
    }
)
@websocket_api.async_response
@_ws_handle_cloud_errors
async def alexa_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get data for a single alexa entity."""
    entity_id: str = msg["entity_id"]

    if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES or not entity_supported_by_alexa(
        hass, entity_id
    ):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            f"{entity_id} not supported by Alexa",
        )
        return

    connection.send_result(msg["id"])


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
    cloud = hass.data[DATA_CLOUD]
    alexa_config = await cloud.client.get_alexa_config()
    entities = alexa_entities.async_get_entities(hass, alexa_config)

    result = [
        {
            "entity_id": entity.entity_id,
            "display_categories": entity.default_display_categories(),
            "interfaces": [ifc.name() for ifc in entity.interfaces()],
        }
        for entity in entities
    ]

    connection.send_result(msg["id"], result)


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
    cloud = hass.data[DATA_CLOUD]
    alexa_config = await cloud.client.get_alexa_config()

    async with asyncio.timeout(10):
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
    cloud = hass.data[DATA_CLOUD]

    async with asyncio.timeout(10):
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
        msg["id"],
        {
            "languages": [
                (language, voice)
                for language, voices in TTS_VOICES.items()
                for voice in voices
            ]
        },
    )
