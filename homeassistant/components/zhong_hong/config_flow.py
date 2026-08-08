"""Config flow for the ZhongHong integration."""

import asyncio
from typing import Any, override

import voluptuous as vol
from zhong_hong_hvac.hub import ZhongHongGateway

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
        ): cv.positive_int,
    }
)

CONNECT_TIMEOUT = 5


async def _async_validate_gateway(
    hass: HomeAssistant, data: dict[str, Any]
) -> str | None:
    """Return an error key, or None when the gateway answered with devices."""
    host: str = data[CONF_HOST]
    port: int = data[CONF_PORT]

    # Probe the socket first. The library retries discovery on its own for
    # minutes before giving up, which is far too long to leave a flow hanging
    # on a mistyped address. The probe has to be closed and waited on before
    # discovery opens its own: the gateway takes one connection at a time and
    # refuses a second one, so a probe still on the way out would make a
    # perfectly reachable gateway look unreachable.
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
    except OSError, TimeoutError:
        return "cannot_connect"

    hub = ZhongHongGateway(host, port, data[CONF_GATEWAY_ADDRESS])
    try:
        addresses = await hass.async_add_executor_job(hub.discovery_ac)
    except OSError:
        LOGGER.debug("Discovery against %s:%s failed", host, port, exc_info=True)
        return "cannot_connect"
    finally:
        await hass.async_add_executor_job(hub.stop_listen)

    if not addresses:
        return "no_devices_found"

    return None


class ZhongHongConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZhongHong."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # A gateway is identified by the endpoint it is reached on and the
            # address it answers to, all three of which the coordinator needs
            # to talk to it.
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_GATEWAY_ADDRESS: user_input[CONF_GATEWAY_ADDRESS],
                }
            )

            if error := await _async_validate_gateway(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle an import from configuration.yaml.

        The gateway is deliberately not contacted here. It accepts a single TCP
        connection at a time, and on a restart it can still be holding the one
        from the previous run, so a reachability check would fail for reasons
        that have nothing to do with the configuration. The YAML platform is
        only set up once per start, so that failure would strand the user on
        YAML until they restarted again. Setting up the entry retries on its
        own, which is where an unreachable gateway belongs.
        """
        self._async_abort_entries_match(
            {
                CONF_HOST: import_data[CONF_HOST],
                CONF_PORT: import_data[CONF_PORT],
                CONF_GATEWAY_ADDRESS: import_data[CONF_GATEWAY_ADDRESS],
            }
        )

        return self.async_create_entry(title=import_data[CONF_HOST], data=import_data)
