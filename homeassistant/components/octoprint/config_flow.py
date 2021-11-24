"""Config flow for OctoPrint integration."""
import logging

from pyoctoprintapi import ApiError, OctoprintClient, OctoprintException
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries, data_entry_flow, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(username="", host="", port=80, path="/", ssl=False):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_PATH, default=path): str,
            vol.Required(CONF_SSL, default=ssl): bool,
        },
        extra=vol.ALLOW_EXTRA,
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OctoPrint."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    api_key_task = None

    def __init__(self) -> None:
        """Handle a config flow for OctoPrint."""
        self.discovery_schema = None
        self._user_input = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # When coming back from the progress steps, the user_input is stored in the
        # instance variable instead of being passed in
        if user_input is None and self._user_input:
            user_input = self._user_input

        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

        if CONF_API_KEY in user_input:
            errors = {}
            try:
                return await self._finish_config(user_input)
            except data_entry_flow.AbortFlow as err:
                raise err from None
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    errors=errors,
                    data_schema=_schema_with_defaults(
                        user_input.get(CONF_USERNAME),
                        user_input[CONF_HOST],
                        user_input[CONF_PORT],
                        user_input[CONF_PATH],
                        user_input[CONF_SSL],
                    ),
                )

        self.api_key_task = None
        return await self.async_step_get_api_key(user_input)

    async def async_step_get_api_key(self, user_input):
        """Get an Application Api Key."""
        if not self.api_key_task:
            self.api_key_task = self.hass.async_create_task(
                self._async_get_auth_key(user_input)
            )
            return self.async_show_progress(
                step_id="get_api_key", progress_action="get_api_key"
            )

        try:
            await self.api_key_task
        except OctoprintException as err:
            _LOGGER.exception("Failed to get an application key: %s", err)
            return self.async_show_progress_done(next_step_id="auth_failed")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to get an application key : %s", err)
            return self.async_show_progress_done(next_step_id="auth_failed")

        # store this off here to pick back up in the user step
        self._user_input = user_input
        return self.async_show_progress_done(next_step_id="user")

    async def _finish_config(self, user_input):
        """Finish the configuration setup."""
        session = async_get_clientsession(self.hass)
        octoprint = OctoprintClient(
            user_input[CONF_HOST],
            session,
            user_input[CONF_PORT],
            user_input[CONF_SSL],
            user_input[CONF_PATH],
        )
        octoprint.set_api_key(user_input[CONF_API_KEY])

        try:
            discovery = await octoprint.get_discovery_info()
        except ApiError as err:
            _LOGGER.error("Failed to connect to printer")
            raise CannotConnect from err

        await self.async_set_unique_id(discovery.upnp_uuid, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_auth_failed(self, user_input):
        """Handle api fetch failure."""
        return self.async_abort(reason="auth_failed")

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle discovery flow."""
        uuid = discovery_info[zeroconf.ATTR_PROPERTIES]["uuid"]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_HOST: discovery_info[zeroconf.ATTR_HOST],
        }

        self.discovery_schema = _schema_with_defaults(
            host=discovery_info[zeroconf.ATTR_HOST],
            port=discovery_info[zeroconf.ATTR_PORT],
            path=discovery_info[zeroconf.ATTR_PROPERTIES][CONF_PATH],
        )

        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle ssdp discovery flow."""
        uuid = discovery_info["UDN"][5:]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        url = URL(discovery_info["presentationURL"])
        self.context["title_placeholders"] = {
            CONF_HOST: url.host,
        }

        self.discovery_schema = _schema_with_defaults(
            host=url.host,
            path=url.path,
            port=url.port,
            ssl=url.scheme == "https",
        )

        return await self.async_step_user()

    async def _async_get_auth_key(self, user_input: dict):
        """Get application api key."""
        session = async_get_clientsession(self.hass)
        octoprint = OctoprintClient(
            user_input[CONF_HOST],
            session,
            user_input[CONF_PORT],
            user_input[CONF_SSL],
            user_input[CONF_PATH],
        )

        try:
            user_input[CONF_API_KEY] = await octoprint.request_app_key(
                "Home Assistant", user_input[CONF_USERNAME], 300
            )
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(
                    flow_id=self.flow_id, user_input=user_input
                )
            )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
