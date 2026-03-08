"""Config flow for Control4 integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials, NotFound, Unauthorized
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from . import Control4ConfigEntry
from .const import (
    CONF_CONTROLLER_UNIQUE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class Control4ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4."""

    VERSION = 1

    async def _async_try_connect(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None, dict[str, str]]:
        """Try to connect to Control4 and return errors, data, and placeholders."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        data: dict[str, Any] | None = None

        host = user_input[CONF_HOST]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Step 1: Authenticate with Control4 cloud API
        account_session = aiohttp_client.async_get_clientsession(self.hass)
        account = C4Account(username, password, account_session)
        try:
            await account.getAccountBearerToken()

            account_controllers = await account.getAccountControllers()
            controller_unique_id = account_controllers["controllerCommonName"]

            director_bearer_token = (
                await account.getDirectorBearerToken(controller_unique_id)
            )["token"]
        except BadCredentials, Unauthorized:
            errors["base"] = "invalid_auth"
            return errors, data, description_placeholders
        except NotFound:
            errors["base"] = "controller_not_found"
            return errors, data, description_placeholders
        except Exception:
            _LOGGER.exception(
                "Unexpected exception during Control4 account authentication"
            )
            errors["base"] = "unknown"
            return errors, data, description_placeholders

        # Step 2: Connect to local Control4 Director
        director_session = aiohttp_client.async_get_clientsession(
            self.hass, verify_ssl=False
        )
        director = C4Director(host, director_bearer_token, director_session)
        try:
            await director.getAllItemInfo()
        except Unauthorized:
            errors["base"] = "director_auth_failed"
            return errors, data, description_placeholders
        except ClientError, TimeoutError:
            errors["base"] = "cannot_connect"
            description_placeholders["host"] = host
            return errors, data, description_placeholders
        except Exception:
            _LOGGER.exception(
                "Unexpected exception during Control4 director connection"
            )
            errors["base"] = "unknown"
            return errors, data, description_placeholders

        # Success - return the data needed for entry creation
        data = {
            CONF_HOST: host,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_CONTROLLER_UNIQUE_ID: controller_unique_id,
        }

        return errors, data, description_placeholders

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            errors, data, description_placeholders = await self._async_try_connect(
                user_input
            )

            if not errors and data is not None:
                controller_unique_id = data[CONF_CONTROLLER_UNIQUE_ID]
                mac = (controller_unique_id.split("_", 3))[2]
                formatted_mac = format_mac(mac)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=controller_unique_id,
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Control4ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle a option flow for Control4."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
