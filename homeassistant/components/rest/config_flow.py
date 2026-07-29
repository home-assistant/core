"""Config Flow for the RESTful integration."""

from re import search
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_RESOURCE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from . import CONFIG_ENTRY_PLATFORMS, create_rest_data_from_config_entry
from .const import (
    CONF_INITIAL_SUBENTRY_TYPE,
    DEFAULT_BINARY_SENSOR_NAME,
    DOCS_URL_AVAILABILTY,
    DOCS_URL_TEMPLATE_DATA_PROCESSING,
    DOMAIN,
    OPTION_NONE,
)
from .data import RestData
from .schema import (
    BINARY_SENSOR_SCHEMA,
    BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
    CREATE_ENTRY_SCHEMA,
    RESOURCE_FLOW_SCHEMA,
    RESOURCE_VALIDATION_SCHEMA,
)

FLOW_SCHEMA = "flow_schema"
VALIDATION_SCHEMA = "validation_schema"


SUBENTRY_CONFIG: dict[Platform, dict[str, Any]] = {
    Platform.BINARY_SENSOR: {
        CONF_NAME: DEFAULT_BINARY_SENSOR_NAME,
        FLOW_SCHEMA: BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
        VALIDATION_SCHEMA: BINARY_SENSOR_SCHEMA,
    }
}


async def _validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    try:
        vol.Schema(RESOURCE_VALIDATION_SCHEMA)(user_input)
        rest: RestData = create_rest_data_from_config_entry(hass, user_input)
        await rest.async_update()
        if rest.last_exception:
            return (
                {"base": "endpoint_error"},
                {"error_message": str(rest.last_exception)},
            )
    except vol.Invalid as ex:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        template_err_index: int = 0
        # This will map the error to the appropriate field as ObjectSelectors do not
        # validate templates by default
        for error in ex.errors if isinstance(ex, vol.MultipleInvalid) else [ex]:
            if isinstance(error.__cause__, TemplateError):
                template_err_index += 1
                errors[str(error.path[0])] = f"template_err_{template_err_index}"
                prepend: str = f"{error.path[1]}: " if len(error.path) > 1 else ""
                placeholders[f"template_err_msg_{template_err_index}"] = (
                    f"{prepend}{error.__cause__!s}"
                )
            else:
                errors[str(error.path[0])] = error.error_message
        return (errors, placeholders)
    return ({}, {})


class RestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the RESTful integration."""

    VERSION = 1
    MINOR_VERSION = 1

    _data: dict[str, Any]
    _next_flow_platform: Platform | None = None

    @override
    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Create subentry flow after creating the main entry."""
        if self._next_flow_platform:
            subentry_result = await self.hass.config_entries.subentries.async_init(
                (result["result"].entry_id, self._next_flow_platform),
                context=SubentryFlowContext(source=SOURCE_USER),
            )
            result["next_flow"] = (
                FlowType.CONFIG_SUBENTRIES_FLOW,
                subentry_result["flow_id"],
            )
        return result

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step in config flow."""
        errors: dict[str, str] = {}
        placeholders: dict[str, Any] = {}
        if user_input is not None:
            errors, placeholders = await _validate_input(self.hass, user_input)
            if not errors:
                if self.source == SOURCE_USER:
                    self._data = user_input
                    return await self.async_step_create_entry()
                return self.async_update_and_abort(
                    self._get_reconfigure_entry(),
                    title=Template(user_input[CONF_RESOURCE], self.hass).async_render(),
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=placeholders,
            data_schema=(
                self.add_suggested_values_to_schema(
                    data_schema=RESOURCE_FLOW_SCHEMA,
                    suggested_values=user_input
                    or (
                        {
                            **self._get_reconfigure_entry().data,
                            CONF_NAME: self._get_reconfigure_entry().title,
                        }
                        if self.source == SOURCE_RECONFIGURE
                        else {}
                    ),
                )
            ),
            last_step=self.source == SOURCE_RECONFIGURE,
        )

    async def async_step_create_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show menu for next flow."""
        if user_input:
            if user_input[CONF_INITIAL_SUBENTRY_TYPE] != OPTION_NONE:
                self._next_flow_platform = user_input[CONF_INITIAL_SUBENTRY_TYPE]
            return self.async_create_entry(
                title=Template(self._data[CONF_RESOURCE], self.hass).async_render(),
                data=self._data,
            )
        return self.async_show_form(
            step_id="create_entry", data_schema=CREATE_ENTRY_SCHEMA
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the config entry."""
        return await self.async_step_user(user_input)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return dict.fromkeys(CONFIG_ENTRY_PLATFORMS, RestSubentryFlow)


class RestSubentryFlow(ConfigSubentryFlow):
    """Base class for subentry flows."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Base step user."""
        if user_input is not None:
            title: str = user_input.get(
                CONF_NAME, SUBENTRY_CONFIG[Platform(self._subentry_type)][CONF_NAME]
            )
            if self.source == SOURCE_USER:
                idx = 0
                for subentry in self._get_entry().subentries.values():
                    if subentry.subentry_type == self._subentry_type:
                        if val := search(r"\d+", subentry.unique_id or "0"):
                            idx = max(int(val.group(0)), idx)
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                    unique_id=f"{self._subentry_type}_{idx + 1}",
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=title,
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "docs_url_availability": DOCS_URL_AVAILABILTY,
                "docs_url_template_data_processing": DOCS_URL_TEMPLATE_DATA_PROCESSING,
                "entry_title": self._get_entry().title,
            },
            data_schema=(
                self.add_suggested_values_to_schema(
                    SUBENTRY_CONFIG[Platform(self._subentry_type)][FLOW_SCHEMA],
                    user_input
                    or (
                        {}
                        if self.source == SOURCE_USER
                        else self._get_reconfigure_subentry().data
                    ),
                )
            ),
            last_step=True,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure the config entry."""
        return await self.async_step_user(user_input)
