"""Config flow for ista EcoTrend integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from pyecotrend_ista import KeycloakError, LoginError, PyEcotrendIsta, ServerError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
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
                info = ista.get_account()
            except ServerError:
                errors["base"] = "cannot_connect"
            except (LoginError, KeycloakError):
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if TYPE_CHECKING:
                    assert info
                title = f"{info['firstName']} {info['lastName']}".strip()
                await self.async_set_unique_id(info["activeConsumptionUnit"])
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            ista = PyEcotrendIsta(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                _LOGGER,
            )

            def get_consumption_units() -> set[str]:
                ista.login()
                consumption_units = ista.get_consumption_unit_details()[
                    "consumptionUnits"
                ]
                return {unit["id"] for unit in consumption_units}

            try:
                consumption_units = await self.hass.async_add_executor_job(
                    get_consumption_units
                )

            except ServerError:
                errors["base"] = "cannot_connect"
            except (LoginError, KeycloakError):
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if reauth_entry.unique_id not in consumption_units:
                    return self.async_abort(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values={
                    CONF_EMAIL: user_input[CONF_EMAIL]
                    if user_input is not None
                    else reauth_entry.data[CONF_EMAIL]
                },
            ),
            description_placeholders={
                CONF_NAME: reauth_entry.title,
                CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
            },
            errors=errors,
        )
