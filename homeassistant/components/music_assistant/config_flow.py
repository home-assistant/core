"""Config flow for MusicAssistant integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from music_assistant_client.auth_helpers import create_long_lived_token, get_server_info
from music_assistant_client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant_models.api import ServerInfoMessage
from music_assistant_models.errors import AuthenticationFailed, InvalidToken
import voluptuous as vol

from homeassistant.components import http
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import AUTH_SCHEMA_VERSION, CONF_TOKEN, DOMAIN, LOGGER

AUTH_CALLBACK_PATH = "/auth/music_assistant/callback"

DEFAULT_TITLE = "Music Assistant"
DEFAULT_URL = "http://mass.local:8095"


class MusicAssistantAuthCallbackView(http.HomeAssistantView):
    """Music Assistant authorization callback view."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = "auth:music_assistant:callback"

    async def get(self, request: http.web.Request) -> http.web.Response:
        """Receive authorization token from Music Assistant."""
        if "flow_id" not in request.query:
            return http.web.Response(text="Missing flow_id parameter", status=400)

        if "token" not in request.query:
            return http.web.Response(text="Missing token parameter", status=400)

        hass = request.app[http.KEY_HASS]
        flow_id = request.query["flow_id"]
        token = request.query["token"]

        # Pass token directly to the config flow via user_input
        await hass.config_entries.flow.async_configure(
            flow_id=flow_id, user_input={CONF_TOKEN: token}
        )

        # Return script to close the popup window
        return http.web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! You can close this window.",
        )


STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_URL): str})
STEP_AUTH_TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


def _parse_zeroconf_server_info(properties: dict[str, str]) -> ServerInfoMessage:
    """Parse zeroconf properties to ServerInfoMessage."""

    def _parse_bool(value: str | bool) -> bool:
        """Parse string boolean."""
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes")

    def _parse_int(value: str | int) -> int:
        """Parse string integer."""
        if isinstance(value, int):
            return value
        return int(value)

    return ServerInfoMessage(
        server_id=properties["server_id"],
        server_version=properties["server_version"],
        schema_version=_parse_int(properties["schema_version"]),
        min_supported_schema_version=_parse_int(
            properties["min_supported_schema_version"]
        ),
        base_url=properties["base_url"],
        homeassistant_addon=_parse_bool(properties["homeassistant_addon"]),
        onboard_done=_parse_bool(properties["onboard_done"]),
    )


async def _get_server_info(hass: HomeAssistant, url: str) -> ServerInfoMessage:
    """Get MA server info for the given URL."""
    session = aiohttp_client.async_get_clientsession(hass)
    return await get_server_info(server_url=url, aiohttp_session=session)


class MusicAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicAssistant."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self.url: str | None = None
        self.token: str | None = None
        self.server_info: ServerInfoMessage | None = None
        self._external_auth_available: bool = False

    def _ensure_callback_view_registered(self) -> None:
        """Ensure the auth callback view is registered."""
        if self.hass.http is not None:
            # register_view is idempotent - safe to call multiple times
            self.hass.http.register_view(MusicAssistantAuthCallbackView())

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.url = user_input[CONF_URL]
            try:
                server_info = await _get_server_info(self.hass, self.url)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidServerVersion:
                errors["base"] = "invalid_server_version"
            except MusicAssistantClientException:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.server_info = server_info
                await self.async_set_unique_id(
                    server_info.server_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(updates={CONF_URL: self.url})

                # Check if authentication is required
                if server_info.schema_version >= AUTH_SCHEMA_VERSION:
                    # Redirect to browser-based authentication
                    return await self.async_step_auth()

                # Old server, no auth needed
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={CONF_URL: self.url},
                )

        suggested_values = user_input
        if suggested_values is None:
            suggested_values = {CONF_URL: DEFAULT_URL}

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Home Assistant add-on discovery.

        This flow is triggered by the Music Assistant add-on.
        """
        # Build URL from add-on discovery info
        # The add-on exposes the API on port 8095, but also has an internal-only
        # port 8094 for the Home Assistant integration to connect to
        host = discovery_info.config["host"]
        port = discovery_info.config["port"]
        self.url = f"http://{host}:{port}"
        try:
            server_info = await _get_server_info(self.hass, self.url)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidServerVersion:
            return self.async_abort(reason="invalid_server_version")
        except MusicAssistantClientException:
            LOGGER.exception("Unexpected exception during add-on discovery")
            return self.async_abort(reason="unknown")

        # Check if server has completed onboarding
        if not server_info.onboard_done:
            return self.async_abort(reason="server_not_ready")

        # We trust the token from hassio discovery and validate it during setup
        self.token = discovery_info.config["auth_token"]

        self.server_info = server_info
        await self.async_set_unique_id(server_info.server_id)
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self.url, CONF_TOKEN: self.token}
        )

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the add-on discovery."""
        if TYPE_CHECKING:
            assert self.url is not None

        if user_input is not None:
            data = {CONF_URL: self.url}
            if self.token:
                data[CONF_TOKEN] = self.token
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data=data,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"url": self.url},
        )

    def _check_external_auth_available(self) -> bool:
        """Check if external auth (redirect) is available."""
        if (req := http.current_request.get()) is None:
            return False
        if req.headers.get("HA-Frontend-Base") is None:
            return False
        return True

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication via redirect to MA login."""
        if TYPE_CHECKING:
            assert self.url is not None

        # Check if we're returning from the external auth step with a token
        if user_input is not None and CONF_TOKEN in user_input:
            # Token was received from callback, store it and complete external step
            self.token = user_input[CONF_TOKEN]
            return self.async_external_step_done(next_step_id="finish_auth")

        # Check if we can use external auth (redirect flow)
        if self._check_external_auth_available():
            # Ensure callback view is registered before redirecting
            self._ensure_callback_view_registered()

            # Build MA login URL with callback
            req = http.current_request.get()
            ha_host = req.headers.get("HA-Frontend-Base")  # type: ignore[union-attr]
            callback_url = f"{ha_host}{AUTH_CALLBACK_PATH}?flow_id={self.flow_id}"
            params = urlencode(
                {"return_url": callback_url, "device_name": "Home Assistant"}
            )
            login_url = f"{self.url}/login?{params}"
            return self.async_external_step(step_id="auth", url=login_url)

        # Fallback to manual token entry if no request context
        return await self.async_step_auth_manual()

    async def async_step_finish_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish authentication after receiving token."""
        if TYPE_CHECKING:
            assert self.url is not None
            assert self.token is not None

        # Exchange short-lived token for long-lived token
        # The OAuth flow gives us a short-lived session token (30 day expiration)
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            LOGGER.debug("Creating long-lived token")
            long_lived_token = await create_long_lived_token(
                self.url,
                self.token,
                "Home Assistant",
                aiohttp_session=session,
            )
            LOGGER.debug("Successfully created long-lived token")
        except (TimeoutError, CannotConnect):
            return self.async_abort(reason="cannot_connect")
        except (AuthenticationFailed, InvalidToken) as err:
            LOGGER.error("Authentication failed: %s", err)
            return self.async_abort(reason="auth_failed")
        except InvalidServerVersion as err:
            LOGGER.error("Invalid server version: %s", err)
            return self.async_abort(reason="invalid_server_version")
        except MusicAssistantClientException:
            LOGGER.exception("Unexpected exception during connection test")
            return self.async_abort(reason="unknown")

        # Check if this is a reauth flow
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            # Update existing entry with new token
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={CONF_URL: self.url, CONF_TOKEN: long_lived_token},
            )

        # Token has been validated through the connection test
        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={CONF_URL: self.url, CONF_TOKEN: long_lived_token},
        )

    async def async_step_auth_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual token entry as fallback."""
        if TYPE_CHECKING:
            assert self.url is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            self.token = user_input[CONF_TOKEN]
            # Token will be validated during setup
            # If invalid, setup will raise ConfigEntryAuthFailed
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={CONF_URL: self.url, CONF_TOKEN: self.token},
            )

        # Show form for manual token entry
        return self.async_show_form(
            step_id="auth_manual",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={"url": self.url},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a zeroconf discovery for a Music Assistant server."""
        try:
            # Parse zeroconf properties (strings) to ServerInfoMessage
            server_info = _parse_zeroconf_server_info(discovery_info.properties)
        except (LookupError, KeyError, ValueError):
            return self.async_abort(reason="invalid_discovery_info")

        LOGGER.debug(
            "Zeroconf discovery: schema=%s, addon=%s, onboard_done=%s",
            server_info.schema_version,
            server_info.homeassistant_addon,
            server_info.onboard_done,
        )

        # For servers with schema >= 28, apply additional filtering
        if server_info.schema_version >= AUTH_SCHEMA_VERSION:
            # Ignore servers running as Home Assistant add-on
            # (they should be discovered through hassio discovery instead)
            if server_info.homeassistant_addon:
                LOGGER.debug("Ignoring add-on server in zeroconf discovery")
                return self.async_abort(reason="already_discovered_addon")

            # Ignore servers that have not completed onboarding yet
            if not server_info.onboard_done:
                LOGGER.debug("Ignoring server that hasn't completed onboarding")
                return self.async_abort(reason="server_not_ready")

        self.url = server_info.base_url
        self.server_info = server_info

        await self.async_set_unique_id(server_info.server_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: self.url})

        try:
            await _get_server_info(self.hass, self.url)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered server."""
        if TYPE_CHECKING:
            assert self.url is not None
            assert self.server_info is not None

        if user_input is not None:
            # Check if authentication is required
            if self.server_info.schema_version >= AUTH_SCHEMA_VERSION:
                # Redirect to browser-based authentication
                return await self.async_step_auth()

            # Old server, no auth needed
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={CONF_URL: self.url},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"url": self.url},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when token is invalid or expired."""
        # Store the URL from the existing entry
        self.url = entry_data[CONF_URL]
        # Get server info to determine auth method
        try:
            self.server_info = await _get_server_info(self.hass, self.url)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidServerVersion:
            return self.async_abort(reason="invalid_server_version")
        except MusicAssistantClientException:
            LOGGER.exception("Unexpected exception during reauth")
            return self.async_abort(reason="unknown")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if TYPE_CHECKING:
            assert self.url is not None
            assert self.server_info is not None

        if user_input is not None:
            # Redirect to auth flow
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"url": self.url},
        )
