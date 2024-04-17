"""Adds config flow for Brother Printer."""

from __future__ import annotations

from typing import Any

from brother import Brother, SnmpError, UnsupportedModelError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_host_valid

from .const import DOMAIN, PRINTER_TYPES
from .utils import get_snmp_engine

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES),
    }
)


class BrotherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brother Printer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.brother: Brother
        self.host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                if not is_host_valid(user_input[CONF_HOST]):
                    raise InvalidHost

                snmp_engine = get_snmp_engine(self.hass)

                brother = await Brother.create(
                    user_input[CONF_HOST], snmp_engine=snmp_engine
                )
                await brother.async_update()

                await self.async_set_unique_id(brother.serial.lower())
                self._abort_if_unique_id_configured()

                title = f"{brother.model} {brother.serial}"
                return self.async_create_entry(title=title, data=user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except (ConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            except SnmpError:
                errors["base"] = "snmp_error"
            except UnsupportedModelError:
                return self.async_abort(reason="unsupported_model")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host

        # Do not probe the device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: self.host})

        snmp_engine = get_snmp_engine(self.hass)
        model = discovery_info.properties.get("product")

        try:
            self.brother = await Brother.create(
                self.host, snmp_engine=snmp_engine, model=model
            )
            await self.brother.async_update()
        except UnsupportedModelError:
            return self.async_abort(reason="unsupported_model")
        except (ConnectionError, SnmpError, TimeoutError):
            return self.async_abort(reason="cannot_connect")

        # Check if already configured
        await self.async_set_unique_id(self.brother.serial.lower())
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        self.context.update(
            {
                "title_placeholders": {
                    "serial_number": self.brother.serial,
                    "model": self.brother.model,
                }
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            title = f"{self.brother.model} {self.brother.serial}"
            return self.async_create_entry(
                title=title,
                data={CONF_HOST: self.host, CONF_TYPE: user_input[CONF_TYPE]},
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES)}
            ),
            description_placeholders={
                "serial_number": self.brother.serial,
                "model": self.brother.model,
            },
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
