"""Config flow for 2N Telekomunikace integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from py2n import Py2NConnectionData, Py2NDevice
from py2n.exceptions import (
    DeviceApiError,
    DeviceConnectionError,
    DeviceUnsupportedError,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.network import is_host_valid

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RESULT_INVALID_HOST = "invalid_host"
RESULT_CANNOT_CONNECT = "cannot_connect"
RESULT_UNSUPPORTED = "unsupported"
RESULT_UNKNOWN = "unknown"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def validate_input(
    hass: HomeAssistant, host: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input."""

    result: dict[str, Any] = {}
    errors: dict[str, str] = {}
    try:
        if not is_host_valid(host):
            raise InvalidHost

        device = await Py2NDevice.create(
            async_get_clientsession(hass),
            Py2NConnectionData(
                host,
                data.get(CONF_USERNAME),
                data.get(CONF_PASSWORD),
            ),
        )
        result["device"] = device
    except InvalidHost:
        errors[CONF_HOST] = RESULT_INVALID_HOST
    except DeviceConnectionError:
        errors["base"] = RESULT_CANNOT_CONNECT
    except DeviceUnsupportedError:
        errors["base"] = RESULT_UNSUPPORTED
    except DeviceApiError as err:
        errors["base"] = err.error.name.lower()
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = RESULT_UNKNOWN

    result["errors"] = errors
    return result


class Py2NDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 2N."""

    VERSION = 1

    entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self: Py2NDeviceConfigFlow, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        result = await validate_input(self.hass, user_input[CONF_HOST], user_input)
        errors = result["errors"]

        if not errors:
            await self.async_set_unique_id(result["device"].data.mac)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=result["device"].data.name, data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if self.entry is None:
            return self.async_abort(reason="reauth_unsuccessful")

        host = self.entry.data[CONF_HOST]

        errors: dict[str, str] = {}
        if user_input is not None:
            result = await validate_input(self.hass, host, user_input)
            errors = result["errors"]

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.entry, data={**self.entry.data, **user_input}
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
