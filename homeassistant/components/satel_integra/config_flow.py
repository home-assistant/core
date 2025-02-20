"""Config flow for Satel Integra."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    DEFAULT_CONF_ARM_HOME_MODE,
    DEFAULT_PORT,
    DOMAIN,
    SatelConfigEntry,
)

_LOGGER = logging.getLogger(__package__)

CONF_ACTION_NUMBER = "number"
CONF_ACTION = "action"

ACTION_EDIT = "edit"
ACTION_ADD = "add"
ACTION_DELETE = "delete"

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CODE): cv.string,
    }
)

CODE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE): cv.string,
    }
)

OPTIONS_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTION_NUMBER): int,
        vol.Required(CONF_ACTION): selector.SelectSelector(
            selector.SelectSelectorConfig(
                translation_key="action_selector",
                mode=selector.SelectSelectorMode.DROPDOWN,
                options=[
                    ACTION_ADD,
                    ACTION_EDIT,
                    ACTION_DELETE,
                ],
            )
        ),
    }
)

PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)


class SatelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Satel Integra config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SatelConfigEntry,
    ) -> SatelOptionsFlow:
        """Create the options flow."""
        return SatelOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            valid = await self.test_connection(
                user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            )

            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={CONF_CODE: user_input.get(CONF_CODE)},
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=CONNECTION_SCHEMA, errors=errors
        )

    async def test_connection(self, host, port) -> bool:
        """Test a connection to the Satel alarm."""
        controller = AsyncSatel(host, port, self.hass.loop)

        result = await controller.connect()

        # Make sure we close the connection again
        controller.close()

        return result


class SatelOptionsFlow(OptionsFlow):
    """Handle Satel options flow."""

    editing_partition: str

    def __init__(self, config_entry: SatelConfigEntry) -> None:
        """Initialize Satel options."""
        self.options = deepcopy(dict(config_entry.options))

    def _create_entry_with_options(self):
        _LOGGER.debug(self.options)
        return self.async_create_entry(data=self.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        return self.async_show_menu(
            step_id="init", menu_options=["general", "partitions"]
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """General step."""
        if user_input is not None:
            self.options[CONF_CODE] = user_input.get(CONF_CODE)
            return self._create_entry_with_options()

        return self.async_show_form(
            step_id="general",
            data_schema=self.add_suggested_values_to_schema(CODE_SCHEMA, self.options),
        )

    async def async_step_partitions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Partitions step."""
        errors = {}
        if user_input is not None:
            selected_partition = str(user_input[CONF_ACTION_NUMBER])
            selected_action = user_input[CONF_ACTION]

            existing_partitions = self.options.get(CONF_DEVICE_PARTITIONS, {})

            if (
                selected_action in (ACTION_EDIT, ACTION_DELETE)
                and selected_partition not in existing_partitions
            ):
                errors["base"] = "unknown_partition"
            elif (
                selected_action == ACTION_ADD
                and selected_partition in existing_partitions
            ):
                errors["base"] = "already_exists"
            elif selected_action == ACTION_DELETE:
                existing_partitions.pop(selected_partition)
                self.options[CONF_DEVICE_PARTITIONS] = existing_partitions
                return self._create_entry_with_options()
            else:
                self.editing_partition = selected_partition
                return await self.async_step_partition_details()

        return self.async_show_form(
            step_id="partitions",
            data_schema=OPTIONS_ACTION_SCHEMA,
            errors=errors,
        )

    async def async_step_partition_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Partition details step."""
        existing_partitions = self.options.get(CONF_DEVICE_PARTITIONS, {})

        if user_input is not None:
            existing_partitions[self.editing_partition] = user_input
            self.options[CONF_DEVICE_PARTITIONS] = existing_partitions
            return self._create_entry_with_options()

        existing_partition_config = existing_partitions.get(self.editing_partition)

        return self.async_show_form(
            step_id="partition_details",
            data_schema=self.add_suggested_values_to_schema(
                PARTITION_SCHEMA, existing_partition_config
            ),
        )
