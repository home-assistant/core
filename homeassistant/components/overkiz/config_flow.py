"""Config flow for Overkiz integration."""
import logging

from aiohttp import ClientError
from pyhoma.client import TahomaClient
from pyhoma.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import HOSTNAME
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_HUB,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HUB,
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    SUPPORTED_ENDPOINTS,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overkiz."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Start the Overkiz config flow."""
        self._reauth_entry = None
        self._default_username = None
        self._default_hub = DEFAULT_HUB

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Handle the flow."""
        return OptionsFlowHandler(config_entry)

    async def async_validate_input(self, user_input):
        """Validate user credentials."""
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        hub = user_input.get(CONF_HUB, DEFAULT_HUB)
        endpoint = SUPPORTED_ENDPOINTS[hub]

        async with TahomaClient(username, password, api_url=endpoint) as client:
            await client.login()

            # Set first gateway as unique id
            gateways = await client.get_gateways()
            if gateways:
                gateway_id = gateways[0].id
                await self.async_set_unique_id(gateway_id)

            # Create new config entry
            if (
                self._reauth_entry is None
                or self._reauth_entry.unique_id != self.unique_id
            ):
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=username, data=user_input)

            # Modify existing entry in reauth scenario
            self.hass.config_entries.async_update_entry(
                self._reauth_entry, data=user_input
            )

            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)

            return self.async_abort(reason="reauth_successful")

    async def async_step_user(self, user_input=None):
        """Handle the initial step via config flow."""
        errors = {}

        if user_input:
            self._default_username = user_input[CONF_USERNAME]
            self._default_hub = user_input[CONF_HUB]

            try:
                return await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except AbortFlow:
                raise
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(exception)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._default_username): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HUB, default=self._default_hub): vol.In(
                        SUPPORTED_ENDPOINTS.keys()
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth if the user credentials have changed."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._default_username = user_input[CONF_USERNAME]
        self._default_hub = user_input[CONF_HUB]

        return await self.async_step_user()

    async def async_step_dhcp(self, discovery_info):
        """Handle DHCP discovery."""
        hostname = discovery_info[HOSTNAME]
        gateway_id = hostname[8:22]

        if self._gateway_already_configured(gateway_id):
            return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    def _gateway_already_configured(self, gateway_id: str):
        """See if we already have a gateway matching the id."""
        device_registry = dr.async_get(self.hass)
        return bool(
            device_registry.async_get_device(
                identifiers={(DOMAIN, gateway_id)}, connections=set()
            )
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Overkiz."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Overkiz options."""
        return await self.async_step_update_interval()

    async def async_step_update_interval(self, user_input=None):
        """Manage the options regarding interval updates."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): vol.All(cv.positive_int, vol.Clamp(min=MIN_UPDATE_INTERVAL))
                }
            ),
        )
