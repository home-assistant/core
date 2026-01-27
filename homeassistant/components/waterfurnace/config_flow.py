"""Config flow for WaterFurnace integration."""

from __future__ import annotations

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
    MINOR_VERSION = 1

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

            gwid = client.gwid
            if not gwid:
                errors["base"] = "cannot_connect"

            if not errors:
                # Set unique ID based on GWID
                await self.async_set_unique_id(gwid)
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

        gwid = client.gwid
        if not gwid:
            # This likely indicates a server-side change, or an implementation bug
            return self.async_abort(reason="cannot_connect")

        # Set unique ID based on GWID
        await self.async_set_unique_id(gwid)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"WaterFurnace {username}",
            data=import_data,
        )
