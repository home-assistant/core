"""Config flow for ista EcoTrend integration."""

from __future__ import annotations

import logging
from typing import Any

from pyecotrend_ista.exception_classes import (
    InternalServerError,
    KeycloakError,
    LoginError,
    ServerError,
)
from pyecotrend_ista.pyecotrend_ista import PyEcotrendIsta
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class IstaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ista EcoTrend."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ista = PyEcotrendIsta(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                _LOGGER,
            )
            try:
                await self.hass.async_add_executor_job(ista.login)
            except (ServerError, InternalServerError):
                errors["base"] = "cannot_connect"
            except (LoginError, KeycloakError):
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = f"{ista._a_firstName} {ista._a_lastName}".strip()  # noqa: SLF001
                await self.async_set_unique_id(ista._uuid)  # noqa: SLF001
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title or "ista EcoTrend", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )
