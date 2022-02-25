"""Config flow for Rabbit Air integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from rabbitair import UdpClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        try:
            zeroconf_instance = await zeroconf.async_get_async_instance(hass)
            with UdpClient(
                data[CONF_HOST], data[CONF_ACCESS_TOKEN], zeroconf=zeroconf_instance
            ) as client:
                info = await client.get_info()
        except Exception as err:
            _LOGGER.debug("Connection attempt failed: %s", err)
            raise
    except ValueError as err:
        # Most likely caused by the invalid access token.
        raise InvalidAccessToken from err
    except OSError as err:
        # Most likely caused by the invalid host.
        raise InvalidHost from err
    except asyncio.TimeoutError as err:
        # Either the host doesn't respond or the auth failed.
        raise TimeoutConnect from err
    except Exception as err:
        # Other possible errors.
        raise CannotConnect from err

    # Return info to store in the config entry.
    return {"title": f"RabbitAir-{info.mac.replace(':', '')}", "mac": info.mac}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rabbit Air."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for the Rabbit Air component."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAccessToken:
            errors["base"] = "invalid_access_token"
        except InvalidHost:
            errors["base"] = "invalid_host"
        except TimeoutConnect:
            errors["base"] = "timeout_connect"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Unexpected exception: %s", err)
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(dr.format_mac(info["mac"]))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccessToken(HomeAssistantError):
    """Error to indicate the access token is not valid."""


class InvalidHost(HomeAssistantError):
    """Error to indicate the host is not valid."""


class TimeoutConnect(HomeAssistantError):
    """Error to indicate the connection attempt is timed out."""


class OptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Rabbit Air."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        scan_interval: int = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=2)),
                }
            ),
        )
