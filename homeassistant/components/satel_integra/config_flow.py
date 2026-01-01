"""Config flow for Satel Integra."""

from __future__ import annotations

import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUT_NUMBER,
    CONF_OUTPUTS,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_CONF_ARM_HOME_MODE,
    DEFAULT_PORT,
    DOMAIN,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
    SatelConfigEntry,
)

_LOGGER = logging.getLogger(__package__)

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

PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)

ZONE_AND_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(
            CONF_ZONE_TYPE, default=BinarySensorDeviceClass.MOTION
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            ),
        ),
    }
)

SWITCHABLE_OUTPUT_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})


class SatelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Satel Integra config flow."""

    VERSION = 2
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SatelConfigEntry,
    ) -> SatelOptionsFlow:
        """Create the options flow."""
        return SatelOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            SUBENTRY_TYPE_PARTITION: PartitionSubentryFlowHandler,
            SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler,
            SUBENTRY_TYPE_OUTPUT: OutputSubentryFlowHandler,
            SUBENTRY_TYPE_SWITCHABLE_OUTPUT: SwitchableOutputSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

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

        if valid:
            subentries: list[ConfigSubentryData] = []

            for partition_number, partition_data in import_config.get(
                CONF_DEVICE_PARTITIONS, {}
            ).items():
                subentries.append(
                    {
                        "subentry_type": SUBENTRY_TYPE_PARTITION,
                        "title": f"{partition_data[CONF_NAME]} ({partition_number})",
                        "unique_id": f"{SUBENTRY_TYPE_PARTITION}_{partition_number}",
                        "data": {
                            CONF_NAME: partition_data[CONF_NAME],
                            CONF_ARM_HOME_MODE: partition_data.get(
                                CONF_ARM_HOME_MODE, DEFAULT_CONF_ARM_HOME_MODE
                            ),
                            CONF_PARTITION_NUMBER: partition_number,
                        },
                    }
                )

            for zone_number, zone_data in import_config.get(CONF_ZONES, {}).items():
                subentries.append(
                    {
                        "subentry_type": SUBENTRY_TYPE_ZONE,
                        "title": f"{zone_data[CONF_NAME]} ({zone_number})",
                        "unique_id": f"{SUBENTRY_TYPE_ZONE}_{zone_number}",
                        "data": {
                            CONF_NAME: zone_data[CONF_NAME],
                            CONF_ZONE_NUMBER: zone_number,
                            CONF_ZONE_TYPE: zone_data.get(
                                CONF_ZONE_TYPE, BinarySensorDeviceClass.MOTION
                            ),
                        },
                    }
                )

            for output_number, output_data in import_config.get(
                CONF_OUTPUTS, {}
            ).items():
                subentries.append(
                    {
                        "subentry_type": SUBENTRY_TYPE_OUTPUT,
                        "title": f"{output_data[CONF_NAME]} ({output_number})",
                        "unique_id": f"{SUBENTRY_TYPE_OUTPUT}_{output_number}",
                        "data": {
                            CONF_NAME: output_data[CONF_NAME],
                            CONF_OUTPUT_NUMBER: output_number,
                            CONF_ZONE_TYPE: output_data.get(
                                CONF_ZONE_TYPE, BinarySensorDeviceClass.MOTION
                            ),
                        },
                    }
                )

            for switchable_output_number, switchable_output_data in import_config.get(
                CONF_SWITCHABLE_OUTPUTS, {}
            ).items():
                subentries.append(
                    {
                        "subentry_type": SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
                        "title": f"{switchable_output_data[CONF_NAME]} ({switchable_output_number})",
                        "unique_id": f"{SUBENTRY_TYPE_SWITCHABLE_OUTPUT}_{switchable_output_number}",
                        "data": {
                            CONF_NAME: switchable_output_data[CONF_NAME],
                            CONF_SWITCHABLE_OUTPUT_NUMBER: switchable_output_number,
                        },
                    }
                )

            return self.async_create_entry(
                title=import_config[CONF_HOST],
                data={
                    CONF_HOST: import_config[CONF_HOST],
                    CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
                },
                options={CONF_CODE: import_config.get(CONF_CODE)},
                subentries=subentries,
            )

        return self.async_abort(reason="cannot_connect")

    async def test_connection(self, host: str, port: int) -> bool:
        """Test a connection to the Satel alarm."""
        controller = AsyncSatel(host, port, self.hass.loop)

        result = await controller.connect()

        # Make sure we close the connection again
        controller.close()

        return result


class SatelOptionsFlow(OptionsFlow):
    """Handle Satel options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        if user_input is not None:
            return self.async_create_entry(data={CONF_CODE: user_input.get(CONF_CODE)})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                CODE_SCHEMA, self.config_entry.options
            ),
        )


class PartitionSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a partition."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add new partition."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_PARTITION}_{user_input[CONF_PARTITION_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_PARTITION_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]} ({user_input[CONF_PARTITION_NUMBER]})",
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PARTITION_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ).extend(PARTITION_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure existing partition."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=f"{user_input[CONF_NAME]} ({subconfig_entry.data[CONF_PARTITION_NUMBER]})",
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                PARTITION_SCHEMA,
                subconfig_entry.data,
            ),
            description_placeholders={
                CONF_PARTITION_NUMBER: subconfig_entry.data[CONF_PARTITION_NUMBER]
            },
        )


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a zone."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add new zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_ZONE}_{user_input[CONF_ZONE_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_ZONE_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]} ({user_input[CONF_ZONE_NUMBER]})",
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ).extend(ZONE_AND_OUTPUT_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure existing zone."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=f"{user_input[CONF_NAME]} ({subconfig_entry.data[CONF_ZONE_NUMBER]})",
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_AND_OUTPUT_SCHEMA, subconfig_entry.data
            ),
            description_placeholders={
                CONF_ZONE_NUMBER: subconfig_entry.data[CONF_ZONE_NUMBER]
            },
        )


class OutputSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a output."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add new output."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_OUTPUT}_{user_input[CONF_OUTPUT_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_OUTPUT_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]} ({user_input[CONF_OUTPUT_NUMBER]})",
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTPUT_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ).extend(ZONE_AND_OUTPUT_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure existing output."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=f"{user_input[CONF_NAME]} ({subconfig_entry.data[CONF_OUTPUT_NUMBER]})",
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_AND_OUTPUT_SCHEMA, subconfig_entry.data
            ),
            description_placeholders={
                CONF_OUTPUT_NUMBER: subconfig_entry.data[CONF_OUTPUT_NUMBER]
            },
        )


class SwitchableOutputSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a switchable output."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add new switchable output."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{SUBENTRY_TYPE_SWITCHABLE_OUTPUT}_{user_input[CONF_SWITCHABLE_OUTPUT_NUMBER]}"

            for existing_subentry in self._get_entry().subentries.values():
                if existing_subentry.unique_id == unique_id:
                    errors[CONF_SWITCHABLE_OUTPUT_NUMBER] = "already_configured"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]} ({user_input[CONF_SWITCHABLE_OUTPUT_NUMBER]})",
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SWITCHABLE_OUTPUT_NUMBER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ).extend(SWITCHABLE_OUTPUT_SCHEMA.schema),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure existing switchable output."""
        subconfig_entry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subconfig_entry,
                title=f"{user_input[CONF_NAME]} ({subconfig_entry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]})",
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                SWITCHABLE_OUTPUT_SCHEMA, subconfig_entry.data
            ),
            description_placeholders={
                CONF_SWITCHABLE_OUTPUT_NUMBER: subconfig_entry.data[
                    CONF_SWITCHABLE_OUTPUT_NUMBER
                ]
            },
        )
