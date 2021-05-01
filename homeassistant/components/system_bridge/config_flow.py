"""Config flow for System Bridge integration."""
import logging
from typing import Any, Dict, Optional, Tuple

import async_timeout
from systembridge import Bridge
from systembridge.client import BridgeClient
from systembridge.exceptions import BridgeAuthenticationException
from systembridge.objects.os import Os
from systembridge.objects.system import System
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import BRIDGE_CONNECTION_ERRORS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_AUTHENTICATE_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=9170): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    bridge = Bridge(
        BridgeClient(aiohttp_client.async_get_clientsession(hass)),
        f"http://{data[CONF_HOST]}:{data[CONF_PORT]}",
        data[CONF_API_KEY],
    )

    hostname = data[CONF_HOST]
    try:
        async with async_timeout.timeout(30):
            bridge_os: Os = await bridge.async_get_os()
            if bridge_os.hostname is not None:
                hostname = bridge_os.hostname
            bridge_system: System = await bridge.async_get_system()
    except BridgeAuthenticationException as exception:
        _LOGGER.info(exception)
        raise InvalidAuth from exception
    except BRIDGE_CONNECTION_ERRORS as exception:
        _LOGGER.info(exception)
        raise CannotConnect from exception

    return {"hostname": hostname, "uuid": bridge_system.uuid.os}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for System Bridge."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._name: Optional[str] = None
        self._input: Optional[Dict[str, Any]] = {}

    async def _async_get_info(
        self, user_input=None
    ) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return None, info

        return errors, None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors, info = await self._async_get_info(user_input)
        if errors is None:
            # Check if already configured
            await self.async_set_unique_id(info["uuid"], raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_HOST: info["hostname"]})

            return self.async_create_entry(title=info["hostname"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_authenticate(self, user_input=None):
        """Handle getting the api-key for authentication."""
        if self._input:
            user_input = {**self._input, **(user_input or {})}
        if user_input is None or user_input.get(CONF_API_KEY, None) is None:
            return self.async_show_form(
                step_id="authenticate",
                data_schema=STEP_AUTHENTICATE_DATA_SCHEMA,
                description_placeholders={"name": self._name},
            )

        errors, info = await self._async_get_info(user_input)
        if errors is None:
            # Check if already configured
            await self.async_set_unique_id(info["uuid"])
            self._abort_if_unique_id_configured(updates={CONF_HOST: info["hostname"]})

            return self.async_create_entry(title=info["hostname"], data=user_input)

        return self.async_show_form(
            step_id="authenticate",
            data_schema=STEP_AUTHENTICATE_DATA_SCHEMA,
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        host = discovery_info["properties"].get("ip", None)
        uuid = discovery_info["properties"].get("uuid", None)

        # Check if already configured
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._name = host
        self._input = {
            CONF_HOST: host,
            CONF_PORT: discovery_info["properties"].get("port", None),
        }

        return await self.async_step_authenticate(self._input)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        if (
            user_input is not None
            and user_input != {}
            and user_input.get(CONF_HOST, None) is not None
            and user_input.get(CONF_PORT, None) is not None
        ):
            self._name = user_input[CONF_HOST]
            self._input = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }

        if self._input != {}:
            user_input = {**self._input, **(user_input or {})}

        errors, info = await self._async_get_info(user_input)
        if errors is None:
            existing_entry = await self.async_set_unique_id(info["uuid"])
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_AUTHENTICATE_DATA_SCHEMA,
            description_placeholders={"name": self._name},
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
