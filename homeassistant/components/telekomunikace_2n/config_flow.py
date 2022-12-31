"""Config flow for 2N Telekomunikace integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from py2n import Py2NConnectionData, Py2NDevice
from py2n.exceptions import DeviceConnectionError, InvalidAuthError
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.network import is_host_valid

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME, default=None): str,
        vol.Optional(CONF_PASSWORD, default=None): str,
    }
)


class Py2NDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 2N."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}
        session = aiohttp.ClientSession()
        try:
            if not is_host_valid(user_input[CONF_HOST]):
                raise InvalidHost

            device = await Py2NDevice.create(
                session,
                options=Py2NConnectionData(
                    ip_address=user_input[CONF_HOST],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                ),
            )
        except InvalidHost:
            errors[CONF_HOST] = "wrong_host"
        except DeviceConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=device.data.name, data=user_input)
        finally:
            await session.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
