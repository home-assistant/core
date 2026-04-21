"""Config flow for WaterFurnace integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class WaterFurnaceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WaterFurnace."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            client = WaterFurnace(username, password)

            try:
                # Login is a blocking call, run in executor
                await self.hass.async_add_executor_job(client.login)
            except WFCredentialError:
                errors["base"] = "invalid_auth"
            except WFException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to WaterFurnace")
                errors["base"] = "unknown"

            if not errors and not client.devices:
                errors["base"] = "no_devices"

            if not errors and client.account_id is None:
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(str(client.account_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"WaterFurnace {username}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            client = WaterFurnace(username, password)

            try:
                await self.hass.async_add_executor_job(client.login)
            except WFCredentialError:
                errors["base"] = "invalid_auth"
            except WFException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"

            if not errors and client.account_id is None:
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(str(client.account_id))
                self._abort_if_unique_id_mismatch(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    title=f"WaterFurnace {username}",
                    data_updates={**reauth_entry.data, **user_input},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        username = import_data[CONF_USERNAME]
        password = import_data[CONF_PASSWORD]

        client = WaterFurnace(username, password)

        try:
            # Login is a blocking call, run in executor
            await self.hass.async_add_executor_job(client.login)
        except WFCredentialError:
            return self.async_abort(reason="invalid_auth")
        except WFException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error importing WaterFurnace configuration")
            return self.async_abort(reason="unknown")

        if not client.devices:
            return self.async_abort(reason="no_devices")

        if client.account_id is None:
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(str(client.account_id))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"WaterFurnace {username}",
            data=import_data,
        )
