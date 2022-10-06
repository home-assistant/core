"""Config flow for Nibe Heat Pump integration."""
from __future__ import annotations

import errno
from typing import Any

from nibe.connection.nibegw import NibeGW
from nibe.exceptions import CoilNotFoundException, CoilReadException, CoilWriteException
from nibe.heatpump import HeatPump, Model
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util.network import is_ipv4_address

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(list(Model.__members__)),
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_LISTENING_PORT): cv.port,
        vol.Required(CONF_REMOTE_READ_PORT): cv.port,
        vol.Required(CONF_REMOTE_WRITE_PORT): cv.port,
    }
)


class FieldError(Exception):
    """Field with invalid data."""

    def __init__(self, message: str, field: str, error: str) -> None:
        """Set up error."""
        super().__init__(message)
        self.field = field
        self.error = error


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    if not is_ipv4_address(data[CONF_IP_ADDRESS]):
        raise FieldError("Not a valid ipv4 address", CONF_IP_ADDRESS, "address")

    heatpump = HeatPump(Model[data[CONF_MODEL]])
    heatpump.initialize()

    connection = NibeGW(
        heatpump,
        data[CONF_IP_ADDRESS],
        data[CONF_REMOTE_READ_PORT],
        data[CONF_REMOTE_WRITE_PORT],
        listening_port=data[CONF_LISTENING_PORT],
    )

    try:
        await connection.start()
    except OSError as exception:
        if exception.errno == errno.EADDRINUSE:
            raise FieldError(
                "Address already in use", "listening_port", "address_in_use"
            ) from exception
        raise

    try:
        coil = heatpump.get_coil_by_name("modbus40-word-swap-48852")
        coil = await connection.read_coil(coil)
        word_swap = coil.value == "ON"
        coil = await connection.write_coil(coil)
    except CoilNotFoundException as exception:
        raise FieldError(
            "Model selected doesn't seem to support expected coils", "base", "model"
        ) from exception
    except CoilReadException as exception:
        raise FieldError("Timeout on read from pump", "base", "read") from exception
    except CoilWriteException as exception:
        raise FieldError("Timeout on writing to pump", "base", "write") from exception
    finally:
        await connection.stop()

    return {
        "title": f"{data[CONF_MODEL]} at {data[CONF_IP_ADDRESS]}",
        CONF_WORD_SWAP: word_swap,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nibe Heat Pump."""

    VERSION = 1

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
        except FieldError as exception:
            LOGGER.debug("Validation error %s", exception)
            errors[exception.field] = exception.error
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            data = {
                **user_input,
                CONF_WORD_SWAP: info[CONF_WORD_SWAP],
                CONF_CONNECTION_TYPE: CONF_CONNECTION_TYPE_NIBEGW,
            }
            return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
