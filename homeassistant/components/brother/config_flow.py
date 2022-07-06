"""Adds config flow for Brother Printer."""
from __future__ import annotations

import ipaddress
import re
from typing import Any

from brother import Brother, SnmpError, UnsupportedModel
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PRINTER_TYPES
from .utils import get_snmp_engine

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES),
    }
)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version in [4, 6]:
            return True
    except ValueError:
        pass
    disallowed = re.compile(r"[^a-zA-Z\d\-]")
    return all(x and not disallowed.search(x) for x in host.split("."))


class BrotherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brother Printer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.brother: Brother
        self.host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                if not host_valid(user_input[CONF_HOST]):
                    raise InvalidHost()

                snmp_engine = get_snmp_engine(self.hass)

                brother = Brother(user_input[CONF_HOST], snmp_engine=snmp_engine)
                await brother.async_update()

                await self.async_set_unique_id(brother.serial.lower())
                self._abort_if_unique_id_configured()

                title = f"{brother.model} {brother.serial}"
                return self.async_create_entry(title=title, data=user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except SnmpError:
                errors["base"] = "snmp_error"
            except UnsupportedModel:
                return self.async_abort(reason="unsupported_model")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host

        # Do not probe the device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: self.host})

        snmp_engine = get_snmp_engine(self.hass)
        model = discovery_info.properties.get("product")

        try:
            self.brother = Brother(self.host, snmp_engine=snmp_engine, model=model)
            await self.brother.async_update()
        except UnsupportedModel:
            return self.async_abort(reason="unsupported_model")
        except (ConnectionError, SnmpError):
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
    ) -> FlowResult:
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


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
