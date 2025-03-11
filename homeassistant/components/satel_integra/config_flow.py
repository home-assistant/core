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
    CONF_OUTPUTS,
    CONF_SWITCHABLE_OUTPUTS,
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
        vol.Required(CONF_ACTION_NUMBER): vol.All(
            int,
            vol.Range(min=1),
        ),
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

SWITCHABLE_OUTPUT_SCHEM = vol.Schema({vol.Required(CONF_NAME): cv.string})


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
                user_input[CONF_HOST], user_input[CONF_PORT]
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

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by import."""

        valid = await self.test_connection(
            import_config[CONF_HOST], import_config.get(CONF_PORT, DEFAULT_PORT)
        )

        _LOGGER.info(import_config)
        _LOGGER.info(valid)

        if valid:
            return self.async_create_entry(
                title=import_config[CONF_HOST],
                data={
                    CONF_HOST: import_config[CONF_HOST],
                    CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
                },
                options={
                    CONF_CODE: import_config.get(CONF_CODE),
                    CONF_DEVICE_PARTITIONS: import_config.get(
                        CONF_DEVICE_PARTITIONS, {}
                    ),
                    CONF_ZONES: import_config.get(CONF_ZONES, {}),
                    CONF_OUTPUTS: import_config.get(CONF_OUTPUTS, {}),
                    CONF_SWITCHABLE_OUTPUTS: import_config.get(
                        CONF_SWITCHABLE_OUTPUTS, {}
                    ),
                },
            )

        return self.async_abort(reason="Failed to connect")

    async def test_connection(self, host, port) -> bool:
        """Test a connection to the Satel alarm."""
        controller = AsyncSatel(host, port, self.hass.loop)

        result = await controller.connect()

        # Make sure we close the connection again
        controller.close()

        return result


class SatelOptionsFlow(OptionsFlow):
    """Handle Satel options flow."""

    editing_entry: str

    def __init__(self, config_entry: SatelConfigEntry) -> None:
        """Initialize Satel options flow."""
        self._initialize_options(config_entry)

        self.partition_options = self.options[CONF_DEVICE_PARTITIONS]
        self.zone_options = self.options[CONF_ZONES]
        self.output_options = self.options[CONF_OUTPUTS]
        self.switchable_output_options = self.options[CONF_SWITCHABLE_OUTPUTS]

    def _initialize_options(self, config_entry: SatelConfigEntry):
        """Initialize default options."""
        self.options = deepcopy(dict(config_entry.options))

        if CONF_DEVICE_PARTITIONS not in self.options:
            self.options[CONF_DEVICE_PARTITIONS] = {}

        if CONF_ZONES not in self.options:
            self.options[CONF_ZONES] = {}

        if CONF_OUTPUTS not in self.options:
            self.options[CONF_OUTPUTS] = {}

        if CONF_SWITCHABLE_OUTPUTS not in self.options:
            self.options[CONF_SWITCHABLE_OUTPUTS] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "partitions",
                "zones",
                "outputs",
                "switchable_outputs",
            ],
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
        """Partition configuration step."""
        errors: dict[str, str] = {}
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
                errors["base"] = "partition_exists"
            elif selected_action == ACTION_DELETE:
                self.partition_options.pop(selected_partition)
                return self.async_create_entry(data=self.options)
            else:
                self.editing_entry = selected_partition
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
            self.partition_options[self.editing_entry] = user_input
            return self.async_create_entry(data=self.options)

        existing_partition_config = self.partition_options.get(self.editing_entry)

        return self.async_show_form(
            step_id="partition_details",
            data_schema=self.add_suggested_values_to_schema(
                PARTITION_SCHEMA, existing_partition_config
            ),
            description_placeholders={"partition_number": self.editing_entry},
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zone configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_zone = str(user_input[CONF_ACTION_NUMBER])
            selected_action = user_input[CONF_ACTION]

            if (
                selected_action in [ACTION_DELETE, ACTION_EDIT]
                and selected_zone not in self.zone_options
            ):
                errors["base"] = "unknown_zone"
            elif selected_action == ACTION_ADD and selected_zone in self.zone_options:
                errors["base"] = "zone_exists"
            elif selected_action == ACTION_DELETE:
                self.zone_options.pop(selected_zone)
                return self.async_create_entry(data=self.options)
            else:
                self.editing_entry = selected_zone
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
            self.zone_options[self.editing_entry] = user_input
            return self.async_create_entry(data=self.options)

        existing_zone_config = self.zone_options.get(self.editing_entry)

        return self.async_show_form(
            step_id="zone_details",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA, existing_zone_config
            ),
            description_placeholders={"zone_number": self.editing_entry},
        )

    async def async_step_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Output configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_output = str(user_input[CONF_ACTION_NUMBER])
            selected_action = user_input[CONF_ACTION]

            if (
                selected_action in [ACTION_DELETE, ACTION_EDIT]
                and selected_output not in self.output_options
            ):
                errors["base"] = "unknown_output"
            elif (
                selected_action == ACTION_ADD and selected_output in self.output_options
            ):
                errors["base"] = "output_exists"
            elif selected_action == ACTION_DELETE:
                self.output_options.pop(selected_output)
                return self.async_create_entry(data=self.options)
            else:
                self.editing_entry = selected_output
                return await self.async_step_output_details()

        return self.async_show_form(
            step_id="outputs",
            data_schema=OPTIONS_ACTION_SCHEMA,
            errors=errors,
        )

    async def async_step_output_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Output details step."""
        if user_input is not None:
            self.output_options[self.editing_entry] = user_input
            return self.async_create_entry(data=self.options)

        existing_output_config = self.output_options.get(self.editing_entry)

        return self.async_show_form(
            step_id="output_details",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA, existing_output_config
            ),
            description_placeholders={"output_number": self.editing_entry},
        )

    async def async_step_switchable_outputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Switchable output configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_switchable_output = str(user_input[CONF_ACTION_NUMBER])
            selected_action = user_input[CONF_ACTION]

            if (
                selected_action in [ACTION_DELETE, ACTION_EDIT]
                and selected_switchable_output not in self.switchable_output_options
            ):
                errors["base"] = "unknown_switchable_output"
            elif (
                selected_action == ACTION_ADD
                and selected_switchable_output in self.switchable_output_options
            ):
                errors["base"] = "switchable_output_exists"
            elif selected_action == ACTION_DELETE:
                self.switchable_output_options.pop(selected_switchable_output)
                return self.async_create_entry(data=self.options)

            else:
                self.editing_entry = selected_switchable_output
                return await self.async_step_switchable_output_details()

        return self.async_show_form(
            step_id="switchable_outputs",
            data_schema=OPTIONS_ACTION_SCHEMA,
            errors=errors,
        )

    async def async_step_switchable_output_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Switchable output details step."""
        if user_input is not None:
            self.switchable_output_options[self.editing_entry] = user_input
            return self.async_create_entry(data=self.options)

        existing_switchable_output_config = self.switchable_output_options.get(
            self.editing_entry
        )

        return self.async_show_form(
            step_id="switchable_output_details",
            data_schema=self.add_suggested_values_to_schema(
                SWITCHABLE_OUTPUT_SCHEM, existing_switchable_output_config
            ),
            description_placeholders={"switchable_output_number": self.editing_entry},
        )
