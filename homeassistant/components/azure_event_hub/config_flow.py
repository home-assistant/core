"""Config flow for azure_event_hub integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    CONF_USE_CONN_STRING,
    DOMAIN,
    STEP_CONN_STRING,
    STEP_SAS,
    STEP_USER,
)
from .models import AzureEventHubClient

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

DEFAULT_OPTIONS = {CONF_SEND_INTERVAL: 5, CONF_MAX_DELAY: 30}


class AEHConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for azure event hub."""

    VERSION: int = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AEHOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._options: Mapping[str, Any] = DEFAULT_OPTIONS
        self._conn_string: bool | None = None

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial user step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(step_id=STEP_USER, data_schema=BASE_SCHEMA)
        self._update_data(user_input, STEP_USER)
        return await self.async_route(STEP_USER)

    async def async_step_conn_string(
        self, user_input: dict[str, Any] = None
    ) -> FlowResult:
        """Handle the connection string steps."""
        if user_input is None:
            return self.async_show_form(
                step_id=STEP_CONN_STRING,
                data_schema=CONN_STRING_SCHEMA,
                description_placeholders=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            )

        self._update_data(user_input, STEP_CONN_STRING)
        errors = await self._validate_data(STEP_CONN_STRING)
        if errors is not None:
            return self.async_show_form(
                step_id=STEP_CONN_STRING,
                data_schema=CONN_STRING_SCHEMA,
                errors=errors,
                description_placeholders=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            )
        return await self.async_route(STEP_CONN_STRING)

    async def async_step_sas(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the sas steps."""
        if user_input is None:
            return self.async_show_form(
                step_id=STEP_SAS,
                data_schema=SAS_SCHEMA,
                description_placeholders=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            )
        self._update_data(user_input, STEP_SAS)
        errors = await self._validate_data(STEP_SAS)
        if errors is not None:
            return self.async_show_form(
                step_id=STEP_SAS,
                data_schema=SAS_SCHEMA,
                errors=errors,
                description_placeholders=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            )

        return await self.async_route(STEP_SAS)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import config from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        self._update_data(import_config, "import")
        return await self.async_route("import")

    async def async_route(self, step_id: str) -> FlowResult:
        """Handle the user_input, check if configured and route to the right next step or create entry."""
        if step_id == STEP_USER and self._conn_string is not None:
            if self._conn_string:
                return await self.async_step_conn_string()
            return await self.async_step_sas()
        return self.async_create_entry(
            title=self._data[CONF_EVENT_HUB_INSTANCE_NAME],
            data=self._data,
            options=self._options,
        )

    async def _validate_data(self, step_id: str) -> dict[str, str] | None:
        """Validate the input."""
        try:
            client = AzureEventHubClient.from_input(**self._data)
        except HomeAssistantError:
            return {"base": f"invalid_{step_id}"}
        except Exception:  # pylint: disable=broad-except
            return {"base": "unknown"}
        try:
            await client.test_connection()
        except EventHubError:
            return {"base": "cannot_connect"}
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error when trying to connect to Azure: %s", exc)
            return {"base": "unknown"}

    def _update_data(self, user_input: dict[str, Any], step_id: str) -> None:
        """Parse the user_input and store in data and options attributes."""
        if step_id == STEP_USER:
            if self._conn_string is None:
                self._conn_string = user_input.pop(CONF_USE_CONN_STRING)
            self._data = user_input
            return
        if step_id in (STEP_CONN_STRING, STEP_SAS):
            self._data.update(user_input)
            return
        if step_id == "import":
            send_interval = user_input.pop(CONF_SEND_INTERVAL, None)
            if send_interval is not None:
                self._options[CONF_SEND_INTERVAL] = send_interval
            max_delay = user_input.pop(CONF_MAX_DELAY, None)
            if max_delay is not None:
                self._options[CONF_MAX_DELAY] = max_delay
            self._data = user_input


class AEHOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle azure event hub options."""

    def __init__(self, config_entry):
        """Initialize AEH options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Manage the SIA options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEND_INTERVAL,
                        default=self.config_entry.options.get(CONF_SEND_INTERVAL),
                    ): int,
                    vol.Required(
                        CONF_MAX_DELAY,
                        default=self.config_entry.options.get(CONF_MAX_DELAY),
                    ): int,
                }
            ),
        )
