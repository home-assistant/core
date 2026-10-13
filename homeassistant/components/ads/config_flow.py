"""Config flow for the ADS integration."""

import logging
from typing import Any, override

import probatio
import pyads

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import CONF_LOCAL_NET_ID, DEFAULT_PORT, DOMAIN
from .hub import local_net_id_probe

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): str,
        probatio.Optional(CONF_IP_ADDRESS): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        probatio.Optional(CONF_LOCAL_NET_ID): str,
    }
)


def _drop_blank_optionals(data: dict[str, Any]) -> dict[str, Any]:
    """Drop optional fields left blank.

    A cleared field is submitted as an empty string, which pyads would take
    as an explicit value instead of falling back to its default.
    """
    return {
        key: value
        for key, value in data.items()
        if key not in (CONF_IP_ADDRESS, CONF_LOCAL_NET_ID) or value
    }


def _validate_connection(data: dict[str, Any]) -> None:
    """Open a connection and read the device state."""
    with local_net_id_probe(data.get(CONF_LOCAL_NET_ID)):
        client = pyads.Connection(
            data[CONF_DEVICE], data[CONF_PORT], data.get(CONF_IP_ADDRESS)
        )
        client.open()
        try:
            client.read_state()
        finally:
            client.close()


class AdsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADS."""

    VERSION = 1

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Validate the connection and return an error key on failure."""
        try:
            await self.hass.async_add_executor_job(_validate_connection, data)
        except ValueError:
            return "invalid_net_id"
        except pyads.ADSError, RuntimeError:
            # A missing local AMS router raises RuntimeError; setup treats that
            # as a connectivity failure too.
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _drop_blank_optionals(user_input)
            if (error := await self._async_validate(user_input)) is None:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=user_input[CONF_DEVICE],
                        data=user_input,
                    )
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE], data=user_input
                )
            errors["base"] = error

        suggested_values = user_input
        if suggested_values is None and self.source == SOURCE_RECONFIGURE:
            suggested_values = dict(self._get_reconfigure_entry().data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the ADS connection."""
        return await self.async_step_user(user_input)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the ADS connection from configuration.yaml."""
        import_data = _drop_blank_optionals(import_data)
        if (error := await self._async_validate(import_data)) is not None:
            return self.async_abort(reason=error)
        return self.async_create_entry(title=import_data[CONF_DEVICE], data=import_data)
