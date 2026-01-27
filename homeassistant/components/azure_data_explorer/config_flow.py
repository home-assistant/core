"""Config flow for Azure Data Explorer integration."""

from __future__ import annotations

import logging
from typing import Any

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import BooleanSelector

from . import AzureDataExplorerClient
from .const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_USE_QUEUED_CLIENT,
    DEFAULT_OPTIONS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADX_CLUSTER_INGEST_URI): str,
        vol.Required(CONF_ADX_DATABASE_NAME): str,
        vol.Required(CONF_ADX_TABLE_NAME): str,
        vol.Required(CONF_APP_REG_ID): str,
        vol.Required(CONF_APP_REG_SECRET): str,
        vol.Required(CONF_AUTHORITY_ID): str,
        vol.Required(CONF_USE_QUEUED_CLIENT, default=False): BooleanSelector(),
    }
)


class ADXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Data Explorer."""

    VERSION = 1

    async def validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """
        client = AzureDataExplorerClient(data)

        try:
            await self.hass.async_add_executor_job(client.test_connection)
        except KustoAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return {"base": "invalid_auth"}
        except KustoServiceError as err:
            _LOGGER.error("Could not connect: %s", err)
            return {"base": "cannot_connect"}

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        data_schema = STEP_USER_DATA_SCHEMA

        if user_input is not None:
            errors = await self.validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    data=user_input,
                    title=f"{user_input[CONF_ADX_CLUSTER_INGEST_URI].replace('https://', '')} / {user_input[CONF_ADX_DATABASE_NAME]} ({user_input[CONF_ADX_TABLE_NAME]})",
                    options=DEFAULT_OPTIONS,
                )

            # Keep previously entered values when we re-show the form after an error.
            data_schema = self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            last_step=True,
        )
