"""Config flow for Nibe Heat Pump integration."""
from __future__ import annotations

from typing import Any

from nibe.connection.modbus import Modbus
from nibe.connection.nibegw import NibeGW
from nibe.exceptions import (
    AddressInUseException,
    CoilNotFoundException,
    CoilReadException,
    CoilReadSendException,
    CoilWriteException,
    CoilWriteSendException,
)
from nibe.heatpump import HeatPump, Model
import voluptuous as vol
import yarl

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_MODBUS,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_MODBUS_UNIT,
    CONF_MODBUS_URL,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
    LOGGER,
)

PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, step=1, max=65535, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Coerce(int),
)

STEP_NIBEGW_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(list(Model.__members__)),
        vol.Required(CONF_IP_ADDRESS): selector.TextSelector(),
        vol.Required(CONF_LISTENING_PORT, default=9999): PORT_SELECTOR,
        vol.Required(CONF_REMOTE_READ_PORT, default=9999): PORT_SELECTOR,
        vol.Required(CONF_REMOTE_WRITE_PORT, default=10000): PORT_SELECTOR,
    }
)


STEP_MODBUS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(list(Model.__members__)),
        vol.Required(CONF_MODBUS_URL): selector.TextSelector(),
        vol.Required(CONF_MODBUS_UNIT, default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
    }
)


class FieldError(Exception):
    """Field with invalid data."""

    def __init__(self, message: str, field: str, error: str) -> None:
        """Set up error."""
        super().__init__(message)
        self.field = field
        self.error = error


async def validate_nibegw_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Validate the user input allows us to connect."""

    heatpump = HeatPump(Model[data[CONF_MODEL]])
    await heatpump.initialize()

    connection = NibeGW(
        heatpump,
        data[CONF_IP_ADDRESS],
        data[CONF_REMOTE_READ_PORT],
        data[CONF_REMOTE_WRITE_PORT],
        listening_port=data[CONF_LISTENING_PORT],
    )

    try:
        await connection.start()
    except AddressInUseException as exception:
        raise FieldError(
            "Address already in use", "listening_port", "address_in_use"
        ) from exception

    try:
        await connection.verify_connectivity()
    except (CoilReadSendException, CoilWriteSendException) as exception:
        raise FieldError(str(exception), CONF_IP_ADDRESS, "address") from exception
    except CoilNotFoundException as exception:
        raise FieldError("Coils not found", "base", "model") from exception
    except CoilReadException as exception:
        raise FieldError("Timeout on read from pump", "base", "read") from exception
    except CoilWriteException as exception:
        raise FieldError("Timeout on writing to pump", "base", "write") from exception
    finally:
        await connection.stop()

    return f"{data[CONF_MODEL]} at {data[CONF_IP_ADDRESS]}", {
        **data,
        CONF_WORD_SWAP: heatpump.word_swap,
        CONF_CONNECTION_TYPE: CONF_CONNECTION_TYPE_NIBEGW,
    }


async def validate_modbus_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Validate the user input allows us to connect."""

    heatpump = HeatPump(Model[data[CONF_MODEL]])
    await heatpump.initialize()

    try:
        connection = Modbus(
            heatpump,
            data[CONF_MODBUS_URL],
            data[CONF_MODBUS_UNIT],
        )
    except ValueError as exc:
        raise FieldError("Not a valid modbus url", CONF_MODBUS_URL, "url") from exc

    await connection.start()

    try:
        await connection.verify_connectivity()
    except (CoilReadSendException, CoilWriteSendException) as exception:
        raise FieldError(str(exception), CONF_MODBUS_URL, "address") from exception
    except CoilNotFoundException as exception:
        raise FieldError("Coils not found", "base", "model") from exception
    except CoilReadException as exception:
        raise FieldError("Timeout on read from pump", "base", "read") from exception
    except CoilWriteException as exception:
        raise FieldError("Timeout on writing to pump", "base", "write") from exception
    finally:
        await connection.stop()

    host = yarl.URL(data[CONF_MODBUS_URL]).host
    return f"{data[CONF_MODEL]} at {host}", {
        **data,
        CONF_CONNECTION_TYPE: CONF_CONNECTION_TYPE_MODBUS,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nibe Heat Pump."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return self.async_show_menu(step_id="user", menu_options=["modbus", "nibegw"])

    async def async_step_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the modbus step."""
        if user_input is None:
            return self.async_show_form(
                step_id="modbus", data_schema=STEP_MODBUS_DATA_SCHEMA
            )

        errors = {}

        try:
            title, data = await validate_modbus_input(self.hass, user_input)
        except FieldError as exception:
            LOGGER.debug("Validation error %s", exception)
            errors[exception.field] = exception.error
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="modbus", data_schema=STEP_MODBUS_DATA_SCHEMA, errors=errors
        )

    async def async_step_nibegw(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the nibegw step."""
        if user_input is None:
            return self.async_show_form(
                step_id="nibegw", data_schema=STEP_NIBEGW_DATA_SCHEMA
            )

        errors = {}

        try:
            title, data = await validate_nibegw_input(self.hass, user_input)
        except FieldError as exception:
            LOGGER.exception("Validation error")
            errors[exception.field] = exception.error
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="nibegw", data_schema=STEP_NIBEGW_DATA_SCHEMA, errors=errors
        )
