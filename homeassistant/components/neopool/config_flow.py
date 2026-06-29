"""Config flow for the NeoPool integration."""

import asyncio
import logging
from typing import Any, override

from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import translation as ha_translation

from .const import CURRENT_VERSION, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN, NAME
from .helpers import async_get_device_serial

_LOGGER = logging.getLogger(__name__)


async def is_host_port_open(host: str, port: int, timeout: int = 3) -> bool:
    """Probe a TCP host:port to verify it accepts connections."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except TimeoutError, OSError:
        return False
    writer.close()
    await writer.wait_closed()
    return True


class NeoPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NeoPool."""

    VERSION = CURRENT_VERSION

    async def _async_validate_connection(self, user_input: dict) -> dict:
        """Validate host/port connectivity and return an errors dict."""
        errors = {}
        host: str = user_input[CONF_HOST]
        port: int = user_input.get(CONF_PORT, DEFAULT_PORT)
        if not await is_host_port_open(host, port):
            errors[CONF_HOST] = "cannot_connect"
        return errors

    async def _async_get_default_title(self) -> str:
        """Return the localized default entry title."""
        try:
            t = await ha_translation.async_get_translations(
                self.hass, self.hass.config.language, "config", {DOMAIN}
            )
            key = f"component.{DOMAIN}.config.step.user.data.name_default"
            return t.get(key) or NAME
        except Exception:  # noqa: BLE001
            return NAME

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional("unit_id", default=DEFAULT_UNIT_ID): int,
                vol.Optional(
                    "modbus_framer",
                    default=DEFAULT_MODBUS_FRAMER,
                ): vol.In(("tcp", "rtu")),
            }
        )
        errors = {}
        if user_input is not None:
            errors = await self._async_validate_connection(user_input)
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                )

            serial_number = await async_get_device_serial(user_input)
            if not serial_number:
                errors[CONF_HOST] = "cannot_read_modbus"
                _LOGGER.warning(
                    "User cannot read from Modbus device at %s:%s",
                    user_input.get(CONF_HOST),
                    user_input.get(CONF_PORT),
                )
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                )

            unique_id = f"neopool_{serial_number}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            _LOGGER.info(
                "Creating new NeoPool config entry (serial: …%s)",
                serial_number[-6:],
            )

            return self.async_create_entry(
                title=await self._async_get_default_title(), data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )
