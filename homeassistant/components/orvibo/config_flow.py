"""Config flow for the Orvibo integration."""

import logging
import re
from typing import Any

from orvibo.s20 import S20, S20Exception
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util.network import is_host_valid

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MAC): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect."""

    if not is_host_valid(data[CONF_HOST]):
        raise InvalidHost

    if not _is_mac_valid(data[CONF_MAC]):
        raise InvalidMac

    try:
        await hass.async_add_executor_job(S20, data[CONF_HOST], data[CONF_MAC])
    except S20Exception:
        raise CannotConnect from None
    except Exception:
        _LOGGER.exception("Error connecting to S20 switch")
        raise CannotConnect from None


def _is_mac_valid(value):
    """Validate MAC address format."""

    mac_address_pattern = r"^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$"
    return re.match(mac_address_pattern, value) is not None


class OrviboConfigFlow(ConfigFlow, domain=DOMAIN):
    """Orvibo config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input:
            user_input[CONF_MAC] = format_mac(user_input[CONF_MAC])

            self._async_abort_entries_match({CONF_MAC: user_input[CONF_MAC]})

            try:
                await validate_input(self.hass, user_input)
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidMac:
                errors["base"] = "invalid_mac"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_MAC: user_input[CONF_MAC],
                    },
                )

        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)


class InvalidHost(HomeAssistantError):
    """Error to indicate an invalid hostname."""


class InvalidMac(HomeAssistantError):
    """Error to indicate an invalid mac address."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
