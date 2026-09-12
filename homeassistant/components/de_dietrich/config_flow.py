"""Config flow for De Dietrich devices."""

import logging
from typing import Any, override

import diematic_modbus
from modbus_connection import ModbusError, ModbusTcpParams
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MESSAGE_SPACING,
    MODBUS_FRAMER,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            vol.Coerce(int),
        ),
    }
)


async def _async_detect(
    hass: HomeAssistant, host: str, port: int, unit_id: int
) -> diematic_modbus.DiematicDetection:
    """Connect to the boiler and read its identity, or raise."""
    params = ModbusTcpParams(host=host, port=port, framer=MODBUS_FRAMER)
    async with async_get_temporary_unit(hass, params, unit_id) as unit:
        unit.set_message_spacing(MESSAGE_SPACING)
        return await diematic_modbus.async_detect(unit)


class DeDietrichConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a De Dietrich config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            connection = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_UNIT_ID: user_input[CONF_UNIT_ID],
            }
            self._async_abort_entries_match(connection)
            try:
                await _async_detect(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_UNIT_ID],
                )
            except diematic_modbus.DiematicProbeError as err:
                outcomes = [
                    block.outcome
                    for block in (
                        *err.detection.base_probe,
                        *err.detection.isystem_probe,
                    )
                ]
                _LOGGER.warning(
                    "Diematic detection failed: %s, probe outcomes: %s",
                    err.detection,
                    outcomes,
                )
                errors["base"] = (
                    "cannot_connect"
                    if any(
                        block.outcome == "error"
                        for block in (
                            *err.detection.base_probe,
                            *err.detection.isystem_probe,
                        )
                    )
                    else "unsupported_device"
                )
                description_placeholders["error"] = str(err)
            except (ModbusError, HomeAssistantError) as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
