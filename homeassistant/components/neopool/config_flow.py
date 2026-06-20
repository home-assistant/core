"""Config flow for the NeoPool integration."""

import asyncio
import logging
from typing import Any

from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import translation as ha_translation

from .const import (
    CONF_FILTRATION_PUMP_POWER,
    CURRENT_VERSION,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    NAME,
)
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


class NeoPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
                vol.Optional(
                    CONF_FILTRATION_PUMP_POWER,
                    default=0,
                ): vol.All(int, vol.Range(min=0)),
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="entry_not_found")
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        current = entry.data

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Optional(
                    "unit_id",
                    default=current.get("unit_id", DEFAULT_UNIT_ID),
                ): int,
                vol.Optional(
                    "modbus_framer",
                    default=current.get("modbus_framer", DEFAULT_MODBUS_FRAMER),
                ): vol.In(("tcp", "rtu")),
            }
        )

        errors = {}
        if user_input is not None:
            errors = await self._async_validate_connection(user_input)
            if not errors:
                if entry.unique_id:
                    serial = await async_get_device_serial({**current, **user_input})
                    if serial and f"neopool_{serial}" != entry.unique_id:
                        errors[CONF_HOST] = "serial_mismatch"
                    elif not serial:
                        errors[CONF_HOST] = "cannot_read_modbus"

            if not errors:
                new_data = {**current, **user_input}
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )
