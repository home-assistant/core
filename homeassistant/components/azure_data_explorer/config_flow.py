"""Config flow for Azure Data Explorer integration."""
# pylint: disable=no-member
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from azure.kusto.data.exceptions import KustoAuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import AzureDataExplorerClient
from .const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_SEND_INTERVAL,
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


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    client = AzureDataExplorerClient(**data)

    try:
        await hass.async_add_executor_job(client.test_connection)

    except KustoAuthenticationError as exp:
        _LOGGER.error(exp)
        return {"base": "invalid_auth"}

    except Exception as exp:  # pylint: disable=broad-except
        _LOGGER.error(exp)
        return {"base": "unknown"}

    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Data Explorer."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = deepcopy(DEFAULT_OPTIONS)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ADXOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._data = user_input
        errors = await validate_input(self.hass, user_input)

        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders=self._data[CONF_ADX_CLUSTER_INGEST_URI],
                last_step=True,
            )

        return self.async_create_entry(
            # Get the Cluster Name from the full url
            title=self.create_title(),
            data=self._data,
            options=self._options,
        )

    def create_title(self):
        """Build the Cluster Title from the URL."""
        url_no_https = str(self._data[CONF_ADX_CLUSTER_INGEST_URI]).split("//")[1]
        cluster_name = str(url_no_https.split(".")[0])

        return cluster_name


class ADXOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle azure adx options."""

    def __init__(self, config_entry):
        """Initialize ADX options flow."""
        self.config_entry = config_entry
        self.options = deepcopy(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the ADX options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEND_INTERVAL,
                        default=self.options.get(CONF_SEND_INTERVAL),
                    ): int
                }
            ),
            last_step=True,
        )
