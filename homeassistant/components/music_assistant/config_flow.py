"""Config flow for MusicAssistant integration."""

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlencode

from music_assistant_client import MusicAssistantClient
from music_assistant_client.auth_helpers import create_long_lived_token, get_server_info
from music_assistant_client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant_models.api import ServerInfoMessage
from music_assistant_models.errors import AuthenticationFailed, InvalidToken
import probatio

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers import aiohttp_client, http
from homeassistant.helpers.config_entry_oauth2_flow import (
    HEADER_FRONTEND_BASE,
    _encode_jwt,
    async_get_redirect_uri,
)
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .app import get_app_manager
from .const import (
    APP_SLUG,
    AUTH_SCHEMA_VERSION,
    DOMAIN,
    HASSIO_DISCOVERY_SCHEMA_VERSION,
    LOGGER,
)

DEFAULT_TITLE = "Music Assistant"
DEFAULT_URL = "http://mass.local:8095"

CONF_USE_APP = "use_app"

# Frontend path of the app ingress page
APP_PANEL_PATH = f"/app/{APP_SLUG}"
APP_START_INTERVAL = 5
APP_START_ROUNDS = 40
ONBOARDING_POLL_INTERVAL = 5
ONBOARDING_POLL_ROUNDS = 720  # an hour


STEP_MANUAL_SCHEMA = probatio.Schema({probatio.Required(CONF_URL): str})
STEP_AUTH_TOKEN_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_TOKEN)): str}
)
STEP_ON_SUPERVISOR_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_USE_APP, default=True): bool}
)


def _parse_zeroconf_server_info(properties: dict[str, str]) -> ServerInfoMessage:
    """Parse zeroconf properties to ServerInfoMessage."""

    return ServerInfoMessage(
        server_id=properties["server_id"],
        server_version=properties["server_version"],
        schema_version=int(properties["schema_version"]),
        min_supported_schema_version=int(properties["min_supported_schema_version"]),
        base_url=properties["base_url"],
        homeassistant_addon=properties["homeassistant_addon"].lower() == "true",
        onboard_done=properties["onboard_done"].lower() == "true",
    )


async def _get_server_info(hass: HomeAssistant, url: str) -> ServerInfoMessage:
    """Get MA server info for the given URL."""
    session = aiohttp_client.async_get_clientsession(hass)
    return await get_server_info(server_url=url, aiohttp_session=session)


async def _test_connection(hass: HomeAssistant, url: str, token: str) -> None:
    """Test connection to MA server with given URL and token."""
    session = aiohttp_client.async_get_clientsession(hass)
    async with MusicAssistantClient(
        server_url=url,
        aiohttp_session=session,
        token=token,
    ) as client:
        # Just executing any command to test the connection.
        # If auth is required and the token is invalid, this will raise.
        await client.send_command("info")


@callback
def _get_frontend_base(hass: HomeAssistant) -> str:
    """Return the base URL of the frontend the user is on.

    The frontend sends its origin with every flow request, which is the
    only URL guaranteed to be reachable from the user's browser.
    """
    if (req := http.current_request.get()) is not None and (
        base := req.headers.get(HEADER_FRONTEND_BASE)
    ):
        return base
    return get_url(hass)


class MusicAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicAssistant."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self.url: str | None = None
        self.token: str | None = None
        self.server_info: ServerInfoMessage | None = None
        self._install_task: asyncio.Task | None = None
        self._start_task: asyncio.Task | None = None
        self._onboarding_task: asyncio.Task | None = None
        self._onboarding_url: str | None = None
        self._removed = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()

        return await self.async_step_manual()

    async def async_step_manual(
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

                # Check if authentication is required for this server
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
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_MANUAL_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is not None:
            if not user_input[CONF_USE_APP]:
                return await self.async_step_manual()

            try:
                app_info = await get_app_manager(self.hass).async_get_addon_info()
            except AddonError as err:
                LOGGER.error(err)
                return self.async_abort(reason="app_info_failed")

            if app_info.state is AddonState.RUNNING:
                return await self.async_step_finish_app_setup()
            if app_info.state is AddonState.NOT_RUNNING:
                return await self.async_step_start_app()
            return await self.async_step_install_app()

        return self.async_show_form(
            step_id="on_supervisor", data_schema=STEP_ON_SUPERVISOR_SCHEMA
        )

    async def async_step_install_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install the Music Assistant app."""
        if self._install_task is None:
            self._install_task = get_app_manager(
                self.hass
            ).async_schedule_install_addon()

        if not self._install_task.done():
            return self.async_show_progress(
                step_id="install_app",
                progress_action="install_app",
                progress_task=self._install_task,
            )

        try:
            await self._install_task
        except AddonError as err:
            LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self._install_task = None

        return self.async_show_progress_done(next_step_id="start_app")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """App installation failed."""
        return self.async_abort(reason="app_install_failed")

    async def async_step_start_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the Music Assistant app."""
        if self._start_task is None:
            self._start_task = self.hass.async_create_task(self._async_start_app())

        if not self._start_task.done():
            return self.async_show_progress(
                step_id="start_app",
                progress_action="start_app",
                progress_task=self._start_task,
            )

        try:
            await self._start_task
        except (AddonError, TimeoutError) as err:
            LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self._start_task = None

        return self.async_show_progress_done(next_step_id="finish_app_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """App start failed."""
        return self.async_abort(reason="app_start_failed")

    async def _async_start_app(self) -> None:
        """Start the Music Assistant app and wait until the server answers."""
        await get_app_manager(self.hass).async_schedule_start_addon()

        for _ in range(APP_START_ROUNDS):
            await asyncio.sleep(APP_START_INTERVAL)
            try:
                await self._async_connect_app()
            except (AddonError, CannotConnect) as err:
                LOGGER.debug(
                    "App not ready yet, waiting %s seconds: %s",
                    APP_START_INTERVAL,
                    err,
                )
                continue
            except MusicAssistantClientException:
                # The server answers, the finish step reports what is wrong with it
                pass
            return

        raise TimeoutError("Timeout waiting for the Music Assistant app to start")

    async def _async_connect_app(self) -> None:
        """Get the app discovery info and fetch the server info with it."""
        discovery_info = await get_app_manager(
            self.hass
        ).async_get_addon_discovery_info()
        self.url = f"http://{discovery_info['host']}:{discovery_info['port']}"
        self.token = discovery_info["auth_token"]
        self.server_info = await _get_server_info(self.hass, self.url)

    async def async_step_finish_app_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry."""
        try:
            await self._async_connect_app()
        except AddonError as err:
            LOGGER.error(err)
            return self.async_abort(reason="app_get_discovery_info_failed")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidServerVersion:
            return self.async_abort(reason="invalid_server_version")
        except MusicAssistantClientException:
            LOGGER.exception("Unexpected exception connecting to the app")
            return self.async_abort(reason="unknown")

        if TYPE_CHECKING:
            assert self.server_info is not None

        await self.async_set_unique_id(
            self.server_info.server_id, raise_on_progress=False
        )
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self.url, CONF_TOKEN: self.token}
        )

        if not self.server_info.onboard_done:
            return await self.async_step_onboarding()

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={CONF_URL: self.url, CONF_TOKEN: self.token},
        )

    async def async_step_onboarding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to finish the initial setup of the app.

        Resumed by the background poll task once the server reports onboarding
        done, or by the frontend; either way the state is verified again here.
        """
        if TYPE_CHECKING:
            assert self.url is not None

        if self._onboarding_task is not None:
            try:
                onboard_done = (
                    await _get_server_info(self.hass, self.url)
                ).onboard_done
            except MusicAssistantClientException:
                onboard_done = False
            if onboard_done:
                self._async_cancel_onboarding_task()
                return self.async_external_step_done(next_step_id="finish_app_setup")

        if self._onboarding_url is None:
            # Only the first entry runs in a frontend request, so keep the URL
            try:
                frontend_base = _get_frontend_base(self.hass)
            except NoURLAvailableError:
                return self.async_abort(
                    reason="no_url_available",
                    description_placeholders={
                        "docs_url": "https://www.home-assistant.io/more-info/no-url-available"
                    },
                )
            self._onboarding_url = f"{frontend_base}{APP_PANEL_PATH}"

        if not self._removed and (
            self._onboarding_task is None or self._onboarding_task.done()
        ):
            self._onboarding_task = self.hass.async_create_task(
                self._async_poll_onboarding()
            )

        return self.async_external_step(step_id="onboarding", url=self._onboarding_url)

    async def _async_poll_onboarding(self) -> None:
        """Poll the server until onboarding is done, then resume the flow."""
        if TYPE_CHECKING:
            assert self.url is not None

        for _ in range(ONBOARDING_POLL_ROUNDS):
            await asyncio.sleep(ONBOARDING_POLL_INTERVAL)
            try:
                server_info = await _get_server_info(self.hass, self.url)
            except MusicAssistantClientException as err:
                LOGGER.debug("Waiting for app onboarding: %s", err)
                continue
            if server_info.onboard_done:
                break
        else:
            LOGGER.debug("Stopped waiting for app onboarding")
            return

        # Resume in a separate task that runs after this one has finished,
        # so the step can cancel or restart this one
        self.hass.async_create_task(self._async_resume_flow(), eager_start=False)

    async def _async_resume_flow(self) -> None:
        """Resume the flow, ignoring that it may have been removed meanwhile."""
        with suppress(UnknownFlow):
            await self.hass.config_entries.flow.async_configure(self.flow_id)

    @callback
    def _async_cancel_onboarding_task(self) -> None:
        """Cancel the onboarding poll task."""
        if self._onboarding_task is not None and not self._onboarding_task.done():
            self._onboarding_task.cancel()
        self._onboarding_task = None

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Home Assistant app discovery.

        This flow is triggered by the Music Assistant app.
        """
        # A user flow either sets up the app entry itself or lets the user
        # choose the app, so do not start a second flow next to it
        if any(
            flow["context"]["source"] == SOURCE_USER
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        # Build URL from app discovery info
        # The app exposes the API on port 8095, but also
        # hosts an internal-only webserver (default at port
        # 8094) for the HA integration to connect to.
        # The info where the internal API is exposed is
        # passed via discovery_info
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
            LOGGER.exception("Unexpected exception during HA app discovery")
            return self.async_abort(reason="unknown")

        # We trust the token from hassio discovery and validate it during setup
        self.token = discovery_info.config["auth_token"]

        self.server_info = server_info

        # Check if there's an existing entry
        if entry := await self.async_set_unique_id(server_info.server_id):
            # Update the entry with new URL and token
            if self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_URL: self.url, CONF_TOKEN: self.token}
            ):
                # Reload the entry if it's in a state that can be reloaded
                if entry.state in (
                    ConfigEntryState.LOADED,
                    ConfigEntryState.SETUP_ERROR,
                    ConfigEntryState.SETUP_RETRY,
                    ConfigEntryState.SETUP_IN_PROGRESS,
                ):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
            elif entry.state is ConfigEntryState.SETUP_RETRY:
                # The server answered, so it is back online: retry setup now
                # instead of waiting for the next backoff interval
                self.hass.config_entries.async_schedule_reload(entry.entry_id)

            # Abort since entry already exists
            return self.async_abort(reason="already_configured")

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the Home Assistant app discovery."""
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
        return self.async_show_form(step_id="hassio_confirm")

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a zeroconf discovery for a Music Assistant server."""
        try:
            # Parse zeroconf properties (strings) to ServerInfoMessage
            server_info = _parse_zeroconf_server_info(discovery_info.properties)
        except LookupError, KeyError, ValueError:
            return self.async_abort(reason="invalid_discovery_info")

        if server_info.schema_version >= HASSIO_DISCOVERY_SCHEMA_VERSION:
            # Ignore servers running as Home Assistant app
            # (they should be discovered through hassio discovery instead)
            if server_info.homeassistant_addon:
                # The app server announcing itself means it is online, so an
                # existing entry waiting to retry setup is reloaded now
                await self.async_set_unique_id(
                    server_info.server_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                LOGGER.debug("Ignoring HA app server in zeroconf discovery")
                return self.async_abort(reason="already_discovered_addon")

        self.url = server_info.base_url
        self.server_info = server_info

        if TYPE_CHECKING:
            assert self.url is not None

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
            # Check if authentication is required for this server
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

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication via redirect to MA login."""
        if TYPE_CHECKING:
            assert self.url is not None

        # Check if we're returning from the external auth step with a token
        if user_input is not None:
            if "error" in user_input:
                return self.async_abort(reason="auth_error")
            # OAuth2 callback sends token as "code" parameter
            if "code" in user_input:
                self.token = user_input["code"]
                return self.async_external_step_done(next_step_id="finish_auth")

        # Check if we can use external auth (redirect flow)
        try:
            redirect_uri = async_get_redirect_uri(self.hass)
        except RuntimeError:
            # No current request context or missing required headers
            return await self.async_step_auth_manual()

        # Use OAuth2 callback URL with JWT-encoded state
        state = _encode_jwt(
            self.hass, {"flow_id": self.flow_id, "redirect_uri": redirect_uri}
        )
        # Music Assistant server will redirect to:
        # {redirect_uri}?state={state}&code={token}
        params = urlencode(
            {
                "return_url": f"{redirect_uri}?state={state}",
                "device_name": "Home Assistant",
            }
        )
        login_url = f"{self.url}/login?{params}"
        return self.async_external_step(step_id="auth", url=login_url)

    async def async_step_finish_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish authentication after receiving token."""
        if TYPE_CHECKING:
            assert self.url is not None
            assert self.token is not None

        # Exchange session token for long-lived token
        # The login flow gives us a session token (short expiration)
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
        except TimeoutError, CannotConnect:
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

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={CONF_URL: self.url, CONF_TOKEN: long_lived_token},
            )

        # Connection has been validated by creating a long-lived token
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
            try:
                # Test the connection with the provided token
                await _test_connection(self.hass, self.url, self.token)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            except InvalidServerVersion:
                return self.async_abort(reason="invalid_server_version")
            except AuthenticationFailed, InvalidToken:
                errors["base"] = "auth_failed"
            except MusicAssistantClientException:
                LOGGER.exception("Unexpected exception during manual auth")
                return self.async_abort(reason="unknown")
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data={CONF_URL: self.url, CONF_TOKEN: self.token},
                    )

                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={CONF_URL: self.url, CONF_TOKEN: self.token},
                )

        return self.async_show_form(
            step_id="auth_manual",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_TOKEN)): str}
            ),
            description_placeholders={"url": self.url},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when token is invalid or expired."""
        self.url = entry_data[CONF_URL]
        # Show confirmation before redirecting to auth
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if TYPE_CHECKING:
            assert self.url is not None

        if user_input is not None:
            # Redirect to auth flow
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"url": self.url},
        )

    @override
    @callback
    def async_remove(self) -> None:
        """Clean up when the flow is removed."""
        self._removed = True
        self._async_cancel_onboarding_task()
