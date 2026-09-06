"""Config flow for the ZhongHong integration."""

from functools import partial
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

# Left to itself the library retries discovery for over five minutes, which is
# what an address that accepts the connection without speaking the protocol
# costs. Waiting that out belongs to the retries that set the entry up, not to
# someone sitting in front of a form. The bound covers connecting as well, so
# an address with nothing behind it is answered for within it too.
DISCOVERY_TIMEOUT = 15


async def _async_validate_gateway(
    hass: HomeAssistant, data: dict[str, Any]
) -> str | None:
    """Return an error key, or None when the gateway answered with devices."""
    host: str = data[CONF_HOST]
    port: int = data[CONF_PORT]

    hub = ZhongHongGateway(host, port, data[CONF_GATEWAY_ADDRESS])
    try:
        addresses = await hass.async_add_executor_job(
            partial(hub.discovery_ac, timeout=DISCOVERY_TIMEOUT)
        )
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
            # address it answers to, all three of which are needed to talk
            # to it.
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

        The YAML can have gone stale: the gateway may have been replaced or
        removed since it was written. Aborting with which part failed leaves
        the platform that started the import able to say so, rather than a
        configuration entry behind that never works.
        """
        self._async_abort_entries_match(
            {
                CONF_HOST: import_data[CONF_HOST],
                CONF_PORT: import_data[CONF_PORT],
                CONF_GATEWAY_ADDRESS: import_data[CONF_GATEWAY_ADDRESS],
            }
        )

        if error := await _async_validate_gateway(self.hass, import_data):
            return self.async_abort(reason=error)

        return self.async_create_entry(title=import_data[CONF_HOST], data=import_data)
