"""Config flow for the Teleinfo integration."""

from __future__ import annotations

import logging
from typing import Any

import serial
from teleinfo import decode, read_frame
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
    }
)


class TeleinfoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Teleinfo."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_serial_port(
        self, serial_port: str
    ) -> tuple[dict[str, str], dict[str, str] | None]:
        """Validate the serial port by reading and decoding a Teleinfo frame.

        Returns a tuple of (errors, decoded_data). On success errors is empty and
        decoded_data contains the label/value pairs. On failure decoded_data is None.
        """
        errors: dict[str, str] = {}
        try:
            frame = await self.hass.async_add_executor_job(read_frame, serial_port)
            decoded_data: dict[str, str] = decode(frame)
        except serial.SerialException:
            errors["base"] = "cannot_connect"
            return errors, None
        except TimeoutError:
            errors["base"] = "timeout_connect"
            return errors, None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return errors, None
        return errors, decoded_data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, decoded_data = await self._validate_serial_port(
                user_input[CONF_SERIAL_PORT]
            )
            if not errors:
                assert decoded_data is not None
                adco = decoded_data["ADCO"]
                await self.async_set_unique_id(adco)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Teleinfo ({user_input[CONF_SERIAL_PORT]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
