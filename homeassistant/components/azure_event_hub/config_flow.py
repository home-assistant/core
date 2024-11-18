"""Config flow for azure_event_hub integration."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .client import AzureEventHubClient
from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    CONF_USE_CONN_STRING,
    DEFAULT_OPTIONS,
    DOMAIN,
    STEP_CONN_STRING,
    STEP_SAS,
    STEP_USER,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_HUB_INSTANCE_NAME): str,
        vol.Optional(CONF_USE_CONN_STRING, default=False): bool,
    }
)

CONN_STRING_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_HUB_CON_STRING): str,
    }
)

SAS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_HUB_NAMESPACE): str,
        vol.Required(CONF_EVENT_HUB_SAS_POLICY): str,
        vol.Required(CONF_EVENT_HUB_SAS_KEY): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SEND_INTERVAL): int,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


async def validate_data(data: dict[str, Any]) -> dict[str, str] | None:
    """Validate the input."""
    client = AzureEventHubClient.from_input(**data)
    try:
        await client.test_connection()
    except EventHubError:
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unknown error")
        return {"base": "unknown"}
    return None


class AEHConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for azure event hub."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = deepcopy(DEFAULT_OPTIONS)
        self._conn_string: bool | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(step_id=STEP_USER, data_schema=BASE_SCHEMA)

        self._conn_string = user_input.pop(CONF_USE_CONN_STRING)
        self._data = user_input

        if self._conn_string:
            return await self.async_step_conn_string()
        return await self.async_step_sas()

    async def async_step_conn_string(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the connection string steps."""
        errors = await self.async_update_and_validate_data(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id=STEP_CONN_STRING,
                data_schema=CONN_STRING_SCHEMA,
                errors=errors,
                description_placeholders={
                    "event_hub_instance_name": self._data[CONF_EVENT_HUB_INSTANCE_NAME]
                },
                last_step=True,
            )

        return self.async_create_entry(
            title=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            data=self._data,
            options=self._options,
        )

    async def async_step_sas(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the sas steps."""
        errors = await self.async_update_and_validate_data(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id=STEP_SAS,
                data_schema=SAS_SCHEMA,
                errors=errors,
                description_placeholders={
                    "event_hub_instance_name": self._data[CONF_EVENT_HUB_INSTANCE_NAME]
                },
                last_step=True,
            )

        return self.async_create_entry(
            title=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            data=self._data,
            options=self._options,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import config from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if CONF_SEND_INTERVAL in import_data:
            self._options[CONF_SEND_INTERVAL] = import_data.pop(CONF_SEND_INTERVAL)
        if CONF_MAX_DELAY in import_data:
            self._options[CONF_MAX_DELAY] = import_data.pop(CONF_MAX_DELAY)
        self._data = import_data
        errors = await validate_data(self._data)
        if errors:
            return self.async_abort(reason=errors["base"])
        return self.async_create_entry(
            title=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            data=self._data,
            options=self._options,
        )

    async def async_update_and_validate_data(
        self, user_input: dict[str, Any] | None
    ) -> dict[str, str] | None:
        """Validate the input."""
        if user_input is None:
            return None
        self._data.update(user_input)
        return await validate_data(self._data)
