"""Config flow for EPH Controls Ember."""

from typing import Any, override

import probatio
from pyephember2.pyephember2 import EphEmber, EphEmberError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


def _get_user_id(username: str, password: str) -> tuple[str | None, dict[str, str]]:
    """Log in to EPH Ember and return the account's user ID, or errors."""
    try:
        ember = EphEmber(username, password)
        user_id = ember.messenging_credentials()["user_id"]
    except EphEmberError:
        return None, {"base": "cannot_connect"}
    except RuntimeError:
        return None, {"base": "invalid_auth"}
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected error logging in to EPH Ember")
        return None, {"base": "unknown"}
    return str(user_id), {}


class EphEmberConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for EPH Controls Ember."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, errors = await self.hass.async_add_executor_job(
                _get_user_id, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration."""
        user_id, errors = await self.hass.async_add_executor_job(
            _get_user_id, import_data[CONF_USERNAME], import_data[CONF_PASSWORD]
        )
        if errors:
            return self.async_abort(reason=errors["base"])
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data[CONF_USERNAME],
            data={
                CONF_USERNAME: import_data[CONF_USERNAME],
                CONF_PASSWORD: import_data[CONF_PASSWORD],
            },
        )
