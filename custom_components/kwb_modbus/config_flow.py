"""Config flow for the KWB Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Step 1: Host and Port (required)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(
            int
        ),
    }
)

# Step 2: Select KWB device (EasyFire 2, EasyFire 3) (required)
# Step 3: Select accessory like boiler (optional)


async def validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the Modbus connection."""
    client = AsyncModbusTcpClient(
        host=data[CONF_HOST], port=data[CONF_PORT], timeout=10
    )

    try:
        # Test connection
        connection_result = await client.connect()
        if not connection_result:
            raise CannotConnect(  # noqa: TRY301
                f"Unable to connect to {data[CONF_HOST]}:{data[CONF_PORT]}"
            )

        # Test basic Modbus communication
        result = await client.read_input_registers(address=8204, count=1)
        if result.isError():
            raise CannotConnect("Failed to read any holding registers")  # noqa: TRY301

    except ModbusException as err:
        raise CannotConnect(f"Modbus connection failed: {err}") from err
    except Exception as err:
        raise CannotConnect(f"Unexpected connection error: {err}") from err
    finally:
        if client.connected:
            client.close()

    # Return info for config entry
    return {"title": f"KWB Modbus {data[CONF_HOST]}"}


class KwbModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KWB Modbus."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize Config flow."""
        self._host_data: dict[str, Any] | {}  # pyright: ignore[reportInvalidTypeForm]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Host and Port configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_connection(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if user_input is not None:
            # Test new connection settings
            try:
                await validate_connection(self.hass, user_input)
            except CannotConnect:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.async_get_options_schema(config_entry.data),
                    errors={"base": "cannot_connect"},
                )
            except Exception:  # noqa: BLE001
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.async_get_options_schema(config_entry.data),
                    errors={"base": "unknown"},
                )

            return self.async_update_reload_and_abort(
                config_entry,
                data_updates=user_input,
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.async_get_options_schema(config_entry.data),
        )

    def async_get_options_schema(self, current_data: dict[str, Any]) -> vol.Schema:
        """Get schema for reconfiguration with current values as defaults."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_PORT, default=current_data.get(CONF_PORT, 502)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_data.get(CONF_SCAN_INTERVAL, 1)
                ): vol.All(vol.Coerce(int)),
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
