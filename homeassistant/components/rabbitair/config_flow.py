"""Config flow for Rabbit Air integration."""

from __future__ import annotations

import logging
from typing import Any

from rabbitair import UdpClient
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        zeroconf_instance = await zeroconf.async_get_async_instance(hass)
        with UdpClient(
            data[CONF_HOST], data[CONF_ACCESS_TOKEN], zeroconf=zeroconf_instance
        ) as client:
            info = await client.get_info()
    except ValueError as err:
        # Most likely caused by an invalid access token.
        raise InvalidAccessToken from err
    except TimeoutError as err:
        # Either the host didn't respond or the auth failed.
        raise TimeoutConnect from err
    except OSError as err:
        # Most likely caused by an invalid host.
        raise InvalidHost from err
    except Exception as err:
        # Other possible errors.
        _LOGGER.exception("Connection attempt failed")
        raise CannotConnect from err

    # Return info to store in the config entry.
    return {"mac": info.mac}


class RabbitAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rabbit Air."""

    VERSION = 1
    _discovered_host: str | None = None

    async def _validate_and_map_errors(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate input and map errors for config flow steps."""
        errors: dict[str, str] = {}
        info: dict[str, Any] | None = None
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
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors, info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, info = await self._validate_and_map_errors(user_input)
            if not errors:
                assert info is not None
                user_input[CONF_MAC] = info["mac"]
                await self.async_set_unique_id(dr.format_mac(info["mac"]))
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
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        mac = dr.format_mac(discovery_info.properties["id"])
        await self.async_set_unique_id(mac)
        host = discovery_info.hostname.rstrip(".")
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._discovered_host = host
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration to update the host address.

        This step allows the user to update the host address for an existing
        Rabbit Air config entry when setup fails. It validates the new host
        address and, if valid, updates the config entry with the new host.
        """
        entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        assert CONF_HOST in entry.data
        current_host = entry.data[CONF_HOST]

        if user_input is not None:
            validate_input_dict = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_ACCESS_TOKEN: entry.data[CONF_ACCESS_TOKEN],
            }
            errors, info = await self._validate_and_map_errors(validate_input_dict)
            if not errors:
                assert info is not None
                expected_mac = entry.unique_id or dr.format_mac(entry.data[CONF_MAC])
                if expected_mac != dr.format_mac(info["mac"]):
                    return self.async_abort(reason="reconfigure_device_mismatch")
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_HOST: user_input[CONF_HOST]}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=current_host): str}
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccessToken(HomeAssistantError):
    """Error to indicate the access token is not valid."""


class InvalidHost(HomeAssistantError):
    """Error to indicate the host is not valid."""


class TimeoutConnect(HomeAssistantError):
    """Error to indicate the connection attempt is timed out."""
