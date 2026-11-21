"""Config flow for the Fenecon Modbus integration."""

import logging
from typing import Any, override

from fenecon_modbus import (
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    FeneconConnectionError,
    FeneconInvalidResponseError,
    FeneconModbusClient,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=255)
            ),
            probatio.Coerce(int),
        ),
    }
)


class FeneconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fenecon Modbus."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                async with FeneconModbusClient(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    unit_id=user_input[CONF_UNIT_ID],
                ) as client:
                    device_info = await client.read_device_info()
            except FeneconConnectionError:
                errors["base"] = "cannot_connect"
            except FeneconInvalidResponseError:
                errors["base"] = "not_openems"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if serial := device_info.manufacturer_ems_serial_number:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                        }
                    )
                return self.async_create_entry(
                    title=device_info.manufacturer_model or "FEMS",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
