"""Config flow for Satel Integra."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_ZONE_TYPE,
    CONF_ZONES,
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
        vol.Required(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(
            CONF_ZONE_TYPE, default=BinarySensorDeviceClass.MOTION
        ): DEVICE_CLASSES_SCHEMA,
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
                    options={
                        CONF_CODE: user_input.get(CONF_CODE),
                        CONF_DEVICE_PARTITIONS: {},
                        CONF_ZONES: {},
                    },
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
    editing_zone: str

    def __init__(self, config_entry: SatelConfigEntry) -> None:
        """Initialize Satel options."""
        self.options = deepcopy(dict(config_entry.options))
        self.partition_options = self.options.get(CONF_DEVICE_PARTITIONS, {})
        self.zone_options = self.options.get(CONF_ZONES, {})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        return self.async_show_menu(
            step_id="init", menu_options=["general", "partitions", "zones"]
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """General step."""
        if user_input is not None:
            self.options[CONF_CODE] = user_input.get(CONF_CODE)
            return self.async_create_entry(data=self.options)

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

            if (
                selected_action in (ACTION_EDIT, ACTION_DELETE)
                and selected_partition not in self.partition_options
            ):
                errors["base"] = "unknown_partition"
            elif (
                selected_action == ACTION_ADD
                and selected_partition in self.partition_options
            ):
                errors["base"] = "already_exists"
            elif selected_action == ACTION_DELETE:
                self.partition_options.pop(selected_partition)
                return self.async_create_entry(data=self.options)
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
        if user_input is not None:
            self.partition_options[self.editing_partition] = user_input
            return self.async_create_entry(data=self.options)

        existing_partition_config = self.partition_options.get(self.editing_partition)

        return self.async_show_form(
            step_id="partition_details",
            data_schema=self.add_suggested_values_to_schema(
                PARTITION_SCHEMA, existing_partition_config
            ),
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zones step."""
        errors = {}
        if user_input is not None:
            selected_zone = str(user_input[CONF_ACTION_NUMBER])
            selected_action = user_input[CONF_ACTION]

            if (
                selected_action in [ACTION_DELETE, ACTION_EDIT]
                and selected_zone not in self.zone_options
            ):
                errors["base"] = "unknown_zone"
            elif selected_action == ACTION_ADD and selected_zone in self.zone_options:
                errors["base"] = "already_exists"
            elif selected_action == ACTION_DELETE:
                self.zone_options.pop(selected_zone)
                return self.async_create_entry(data=self.options)
            else:
                self.editing_zone = selected_zone
                return await self.async_step_zone_details()

        return self.async_show_form(
            step_id="zones",
            data_schema=OPTIONS_ACTION_SCHEMA,
            errors=errors,
        )

    async def async_step_zone_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zone details step."""
        if user_input is not None:
            _LOGGER.info(user_input)
            _LOGGER.info(self.options)
            self.zone_options[self.editing_zone] = user_input
            return self.async_create_entry(data=self.options)

        existing_zone_config = self.zone_options.get(self.editing_zone)

        return self.async_show_form(
            step_id="zone_details",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA, existing_zone_config
            ),
        )
