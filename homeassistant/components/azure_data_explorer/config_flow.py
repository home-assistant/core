"""Config flow for Azure Data Explorer integration."""

from __future__ import annotations

import logging
from typing import Any

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from . import AzureDataExplorerClient
from .const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_USE_FREE,
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
        vol.Optional(CONF_USE_FREE, default=False): bool,
    }
)


class ADXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Data Explorer."""

    VERSION = 1

    async def validate_input(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """
        client = AzureDataExplorerClient(data)

        try:
            await self.hass.async_add_executor_job(client.test_connection)

        except KustoAuthenticationError as exp:
            _LOGGER.error(exp)
            return {"base": "invalid_auth"}

        except KustoServiceError as exp:
            _LOGGER.error(exp)
            return {"base": "cannot_connect"}

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict = {}
        if user_input:
            errors = await self.validate_input(user_input)  # type: ignore[assignment]
            if not errors:
                return self.async_create_entry(
                    data=user_input,
                    title=user_input[CONF_ADX_CLUSTER_INGEST_URI].replace(
                        "https://", ""
                    ),
                    options=DEFAULT_OPTIONS,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            last_step=True,
        )
