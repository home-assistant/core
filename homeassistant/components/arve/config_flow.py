"""Config flow for Arve integration."""

from __future__ import annotations

import logging
from typing import Any

from asyncarve import Arve, ArveConnectionError, ArveCustomer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ArveConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arve."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            arve = Arve(
                user_input[CONF_ACCESS_TOKEN],
                user_input[CONF_CLIENT_SECRET],
            )
            try:
                customer: ArveCustomer = await arve.get_customer_id()
            except ArveConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(customer.customerId)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Arve",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )
