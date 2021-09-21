"""Tesla Config Flow."""
import datetime
import logging
from typing import Any, Dict, List, Optional

from aiohttp import web, web_response
from aiohttp.web_exceptions import HTTPBadRequest
from homeassistant import config_entries, core, exceptions
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from teslajsonpy import Controller as TeslaAPI
from teslajsonpy.exceptions import IncompleteCredentials, TeslaException
from teslajsonpy.teslaproxy import TeslaProxy
import voluptuous as vol
from yarl import URL

from .const import (  # pylint: disable=unused-import
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    AUTH_PROXY_NAME,
    AUTH_PROXY_PATH,
    CONF_EXPIRATION,
    CONF_WAKE_ON_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    ERROR_URL_NOT_DETECTED,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TeslaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Handle a config flow for Tesla."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    proxy: TeslaProxy = None
    proxy_view: Optional["TeslaAuthorizationProxyView"] = None
    data: Optional[Dict[str, Any]] = None
    warning_shown: bool = False
    callback_url: Optional[URL] = None
    controller: Optional[TeslaAPI] = None

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not self.warning_shown:
            self.warning_shown = True
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
                errors={},
                description_placeholders={},
            )
        return await self.async_step_start_oauth()

    async def async_step_reauth(self, data):
        """Handle configuration by re-auth."""
        self.warning_shown = False
        return await self.async_step_user()

    async def async_step_start_oauth(self, user_input=None):
        """Start oauth step for login."""
        self.warning_shown = False
        self.controller = TeslaAPI(
            websession=None,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        host_url: URL = self.controller.get_oauth_url()
        try:
            hass_proxy_url: URL = URL(
                get_url(self.hass, prefer_external=True)
            ).with_path(AUTH_PROXY_PATH)

            TeslaConfigFlow.proxy: TeslaProxy = TeslaProxy(
                proxy_url=hass_proxy_url,
                host_url=host_url,
            )
            TeslaConfigFlow.callback_url: URL = (
                URL(get_url(self.hass, prefer_external=True))
                .with_path(AUTH_CALLBACK_PATH)
                .with_query({"flow_id": self.flow_id})
            )
        except NoURLAvailableError:
            self.warning_shown = False
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
                errors={"base": ERROR_URL_NOT_DETECTED},
                description_placeholders={},
            )

        proxy_url: URL = self.proxy.access_url().with_query(
            {"config_flow_id": self.flow_id, "callback_url": str(self.callback_url)}
        )

        if not self.proxy_view:
            TeslaConfigFlow.proxy_view = TeslaAuthorizationProxyView(
                self.proxy.all_handler
            )
        self.hass.http.register_view(TeslaAuthorizationCallbackView())
        self.hass.http.register_view(self.proxy_view)
        return self.async_external_step(step_id="check_proxy", url=str(proxy_url))

    async def async_step_check_proxy(self, user_input=None):
        """Check status of oauth response for login."""
        self.data = user_input
        self.proxy_view.reset()
        return self.async_external_step_done(next_step_id="finish_oauth")

    async def async_step_finish_oauth(self, user_input=None):
        """Finish auth."""
        info = {}
        errors = {}
        self.controller.set_authorization_code(self.data.get("code", ""))
        self.controller.set_authorization_domain(self.data.get("domain", ""))
        try:
            info = await validate_input(self.hass, info, self.controller)
        except CannotConnect:
            errors["base"] = "cannot_connect"
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            return self.async_abort(reason="invalid_auth")
        # convert from teslajsonpy to HA keys
        if info:
            info = {
                CONF_TOKEN: info["refresh_token"],
                CONF_ACCESS_TOKEN: info[CONF_ACCESS_TOKEN],
                CONF_EXPIRATION: info[CONF_EXPIRATION],
            }
        await self.proxy.reset_data()
        if info and not errors:
            existing_entry = self._async_entry_for_username(self.data[CONF_USERNAME])
            if existing_entry and existing_entry.data == info:
                return self.async_abort(reason="already_configured")

            if existing_entry:
                self.hass.config_entries.async_update_entry(existing_entry, data=info)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(title=self.data[CONF_USERNAME], data=info)
        return self.async_abort(reason="login_failed")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    @callback
    def _async_entry_for_username(self, username):
        """Find an existing entry for a username."""
        for entry in self._async_current_entries():
            if entry.title == username:
                return entry
        return None


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Tesla."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_WAKE_ON_START,
                    default=self.config_entry.options.get(
                        CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def validate_input(hass: core.HomeAssistant, data, controller: TeslaAPI = None):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    config = {}

    try:
        if not controller:
            controller = TeslaAPI(
                websession=None,
                email=data.get(CONF_USERNAME),
                password=data.get(CONF_PASSWORD),
                refresh_token=data.get(CONF_TOKEN),
                access_token=data.get(CONF_ACCESS_TOKEN),
                expiration=data.get(CONF_EXPIRATION, 0),
                update_interval=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        config = await controller.connect(
            wake_if_asleep=data.get(CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START),
            test_login=True,
        )
    except TeslaException as ex:
        if ex.code == HTTP_UNAUTHORIZED or isinstance(ex, IncompleteCredentials):
            _LOGGER.error("Invalid credentials: %s", ex.message)
            raise InvalidAuth() from ex
        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
        raise CannotConnect() from ex
    _LOGGER.debug("Credentials successfully connected to the Tesla API")
    return config


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class TeslaAuthorizationCallbackView(HomeAssistantView):
    """Handle callback from external auth."""

    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME
    requires_auth = False

    async def get(self, request: web.Request):
        """Receive authorization confirmation."""
        hass = request.app["hass"]
        try:
            await hass.config_entries.flow.async_configure(
                flow_id=request.query["flow_id"],
                user_input=request.query,
            )
        except (KeyError, UnknownFlow) as ex:
            _LOGGER.debug("Callback flow_id is invalid")
            raise HTTPBadRequest() from ex
        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )


class TeslaAuthorizationProxyView(HomeAssistantView):
    """Handle proxy connections."""

    url: str = AUTH_PROXY_PATH
    extra_urls: List[str] = [f"{AUTH_PROXY_PATH}/{{tail:.*}}"]
    name: str = AUTH_PROXY_NAME
    requires_auth: bool = False
    handler: web.RequestHandler = None
    known_ips: Dict[str, datetime.datetime] = {}
    auth_seconds: int = 300
    cors_allowed = False

    def __init__(self, handler: web.RequestHandler):
        """Initialize routes for view.

        Args:
            handler (web.RequestHandler): Handler to apply to all method types

        """
        TeslaAuthorizationProxyView.handler = handler
        for method in ("get", "post", "delete", "put", "patch", "head", "options"):
            setattr(self, method, self.check_auth())

    @classmethod
    def check_auth(cls):
        """Wrap access control into the handler."""

        async def wrapped(request, **kwargs):
            """Wrap the handler to require knowledge of config_flow_id."""
            hass = request.app["hass"]
            success = False
            if (
                request.remote not in cls.known_ips
                or (datetime.datetime.now() - cls.known_ips.get(request.remote)).seconds
                > cls.auth_seconds
            ):
                try:
                    flow_id = request.url.query["config_flow_id"]
                except KeyError as ex:
                    raise Unauthorized() from ex
                for flow in hass.config_entries.flow.async_progress():
                    if flow["flow_id"] == flow_id:
                        _LOGGER.debug(
                            "Found flow_id; adding %s to known_ips for %s seconds",
                            request.remote,
                            cls.auth_seconds,
                        )
                        success = True
                if not success:
                    raise Unauthorized()
                cls.known_ips[request.remote] = datetime.datetime.now()
            return await cls.handler(request, **kwargs)

        return wrapped

    @classmethod
    def reset(cls) -> None:
        """Reset the view."""
        cls.known_ips = {}
