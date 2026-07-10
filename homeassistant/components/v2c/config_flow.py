"""Config flow for V2C integration."""

import logging
from typing import Any, override

from pytrydan import Trydan
from pytrydan.exceptions import TrydanError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_CONTRACTED_POWER_ENTITY,
    CONF_POWER_DEVIATION_ENTITY,
    CONF_PV_AVAILABLE,
    DOMAIN,
)
from .coordinator import V2CConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class V2CConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for V2C."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            evse = Trydan(
                user_input[CONF_HOST],
                client=get_async_client(self.hass, verify_ssl=False),
            )

            try:
                data = await evse.get_data()

            except TrydanError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if data.ID:
                    await self.async_set_unique_id(data.ID)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"EVSE {user_input[CONF_HOST]}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            evse = Trydan(
                host,
                client=get_async_client(self.hass, verify_ssl=False),
            )
            try:
                data = await evse.get_data()
            except TrydanError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if data.ID:
                    await self.async_set_unique_id(data.ID)
                    self._abort_if_unique_id_mismatch(reason="another_device")

                return self.async_update_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: V2CConfigEntry,
    ) -> V2COptionsFlowHandler:
        """Create the options flow."""
        return V2COptionsFlowHandler()


class V2COptionsFlowHandler(OptionsFlow):
    """Handle a V2C options flow."""

    _pv_available: bool = False

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        options = self.config_entry.options

        if user_input is not None:
            self._pv_available = user_input[CONF_PV_AVAILABLE]
            if self._pv_available:
                return await self.async_step_pv()
            return self.async_create_entry(data={CONF_PV_AVAILABLE: False})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PV_AVAILABLE,
                        default=options.get(CONF_PV_AVAILABLE, False),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_pv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the helper entities."""
        options = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(data={CONF_PV_AVAILABLE: True, **user_input})

        number_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[Platform.NUMBER, "input_number"])
        )
        data_schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_POWER_DEVIATION_ENTITY): number_selector,
                    vol.Required(CONF_CONTRACTED_POWER_ENTITY): number_selector,
                }
            ),
            options,
        )

        return self.async_show_form(step_id="pv", data_schema=data_schema)
