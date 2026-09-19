"""Config flow for the ZhongHong integration."""

from functools import partial
from typing import Any, override

import probatio
from zhong_hong_hvac.hub import ZhongHongGateway

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    ALL_FAN_MODES,
    CONF_FAN_MODES,
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        probatio.Optional(
            CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
        ): cv.positive_int,
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_FAN_MODES): SelectSelector(
            SelectSelectorConfig(
                options=ALL_FAN_MODES,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="fan_modes",
            )
        )
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

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ZhongHongOptionsFlow()

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


class ZhongHongOptionsFlow(OptionsFlowWithReload):
    """Handle the ZhongHong options.

    The fan speeds are chosen here because the protocol cannot report which of
    its five speeds a unit has: one that lacks a speed looks the same as one
    that never ran at it. Choosing them drops the speeds a unit does not have,
    which would otherwise be offered and do nothing when picked.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose the fan speeds their air conditioners have."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # The selector cannot enforce a minimum on its own, so an empty
            # choice is caught here to keep an air conditioner from being left
            # with no speed to offer.
            if user_input[CONF_FAN_MODES]:
                return self.async_create_entry(data=user_input)
            errors[CONF_FAN_MODES] = "no_fan_modes_selected"

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                user_input
                or {
                    CONF_FAN_MODES: self.config_entry.options.get(
                        CONF_FAN_MODES, ALL_FAN_MODES
                    )
                },
            ),
            errors=errors,
        )
