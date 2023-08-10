"""Config flow for Rabbit Air integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from rabbitair import UdpClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
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
    except asyncio.TimeoutError as err:
        # Either the host doesn't respond or the auth failed.
        raise TimeoutConnect from err
    except OSError as err:
        # Most likely caused by the invalid host.
        raise InvalidHost from err
    except Exception as err:
        # Other possible errors.
        raise CannotConnect from err

    # Return info to store in the config entry.
    return {"mac": info.mac}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rabbit Air."""

    VERSION = 1

    _discovered_host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
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
                user_input[CONF_MAC] = info["mac"]
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title="Rabbit Air", data=user_input)

        user_input = user_input or {}
        host = user_input.get(CONF_HOST, self._discovered_host)
        token = user_input.get(CONF_ACCESS_TOKEN)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_ACCESS_TOKEN, default=token): vol.All(
                        str, vol.Length(min=32, max=32)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        mac = discovery_info.properties["id"]
        mac = ":".join(mac[i : i + 2] for i in range(0, 12, 2))
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()
        self._discovered_host = discovery_info.hostname.rstrip(".")
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccessToken(HomeAssistantError):
    """Error to indicate the access token is not valid."""


class InvalidHost(HomeAssistantError):
    """Error to indicate the host is not valid."""


class TimeoutConnect(HomeAssistantError):
    """Error to indicate the connection attempt is timed out."""
