"""Config Flow for the RESTful integration."""

from collections.abc import Callable
from functools import partial
from re import search
from types import MethodType
from typing import Any, override

from voluptuous import Invalid

from homeassistant.components.sensor import CONF_STATE_CLASS

# pylint: disable=home-assistant-component-root-import
from homeassistant.components.template.config_flow import (
    _validate_state_class,
    _validate_unit,
)

# pylint: enable=home-assistant-component-root-import
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
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_METHOD,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.template import Template

from . import CONFIG_ENTRY_PLATFORMS, create_rest_data_from_config_entry
from .const import (
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    DEFAULT_BINARY_SENSOR_NAME,
    DEFAULT_SENSOR_NAME,
    DOCS_URL_AVAILABILTY,
    DOCS_URL_JSONPATH,
    DOCS_URL_TEMPLATE_DATA_PROCESSING,
    DOCS_URL_XML_CONVERT_SPEC,
    DOMAIN,
)
from .data import RestData
from .schema import (
    BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
    RESOURCE_FLOW_SCHEMA,
    SENSOR_SUBENTRY_FLOW_SCHEMA,
)
from .util import parse_json_attributes_raise_error

FLOW_SCHEMA = "flow_schema"
VALIDATOR = "validator"
NO_PLATFORM = "none"


def _validate_sensor_input(
    input: dict[str, Any], rest: RestData
) -> tuple[dict[str, str], dict[str, str]]:
    """Validate input for sensor subentry."""
    errors: dict[str, str] = {}
    placeholders: dict[str, str] = {}
    if CONF_JSON_ATTRS in input:
        attrs = [item["item"] for item in input[CONF_JSON_ATTRS]]
        try:
            parse_json_attributes_raise_error(
                rest.data, attrs, input.get(CONF_JSON_ATTRS_PATH)
            )
        except HomeAssistantError as ex:
            if ex.translation_key is not None:
                if ex.translation_key == "no_json":
                    errors["base"] = ex.translation_key
                else:
                    errors[
                        CONF_JSON_ATTRS_PATH
                        if ex.translation_key != "attrs_not_found"
                        else CONF_JSON_ATTRS
                    ] = ex.translation_key
                    placeholders = ex.translation_placeholders or {}
        try:
            _validate_unit(input)
        except Invalid as ex:
            errors[CONF_UNIT_OF_MEASUREMENT] = str(ex)
        try:
            _validate_state_class(input)
        except Invalid as ex:
            errors[CONF_STATE_CLASS] = str(ex)

    return errors, placeholders


SUBENTRY_CONFIG: dict[Platform, dict[str, Any]] = {
    Platform.BINARY_SENSOR: {
        CONF_NAME: DEFAULT_BINARY_SENSOR_NAME,
        FLOW_SCHEMA: BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
        VALIDATOR: None,
    },
    Platform.SENSOR: {
        CONF_NAME: DEFAULT_SENSOR_NAME,
        FLOW_SCHEMA: SENSOR_SUBENTRY_FLOW_SCHEMA,
        VALIDATOR: _validate_sensor_input,
    },
}


class RestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the RESTful integration."""

    VERSION = 1
    MINOR_VERSION = 1

    _data: dict[str, Any]
    _next_flow_platform: Platform | str
    _title: str

    @override
    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Create subentry flow after creating the main entry."""
        if self._next_flow_platform != NO_PLATFORM:
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
        placeholders: dict[str, str] = {}
        if user_input is not None:
            rest = create_rest_data_from_config_entry(self.hass, user_input)
            await rest.async_update()
            if rest.last_exception:
                errors["base"] = "endpoint_error"
                placeholders["error_message"] = str(rest.last_exception)
            if not errors:
                self._title = f"{user_input[CONF_METHOD]}-{Template(user_input[CONF_RESOURCE], self.hass).async_render()}"
                if self.source == SOURCE_USER:
                    self._data = user_input
                    return await self.async_step_subentries_menu()
                return self.async_update_and_abort(
                    self._get_reconfigure_entry(),
                    title=self._title,
                    data=user_input,
                )
        suggested_values = user_input or (
            self._get_reconfigure_entry().data
            if self.source == SOURCE_RECONFIGURE
            else {}
        )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=placeholders,
            data_schema=(
                self.add_suggested_values_to_schema(
                    data_schema=RESOURCE_FLOW_SCHEMA(
                        CONF_AUTHENTICATION not in suggested_values
                        or CONF_USERNAME not in suggested_values[CONF_AUTHENTICATION]
                    ),
                    suggested_values=suggested_values,
                )
            ),
            last_step=self.source == SOURCE_RECONFIGURE,
        )

    async def async_step_subentries_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show menu for subentry creation."""

        # Add steps dynamically
        async def _async_subentry_step(
            self: RestConfigFlow, user_input: dict[str, Any] | None, platform: str
        ) -> ConfigFlowResult:
            return await self.async_step_create_entry({CONF_PLATFORM: platform})

        menu_options = [*CONFIG_ENTRY_PLATFORMS, NO_PLATFORM]
        for platform in menu_options:
            setattr(
                self,
                f"async_step_{platform}",
                MethodType(partial(_async_subentry_step, platform=platform), self),
            )

        return self.async_show_menu(
            step_id="subentries_menu",
            menu_options=menu_options,
            description_placeholders={"entry_title": self._title},
        )

    async def async_step_create_entry(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Show menu for next flow."""
        self._next_flow_platform = user_input[CONF_PLATFORM]
        return self.async_create_entry(
            title=self._title,
            data=self._data,
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
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            validator: (
                Callable[
                    [dict[str, Any], RestData], tuple[dict[str, str], dict[str, str]]
                ]
                | None
            ) = SUBENTRY_CONFIG[Platform(self._subentry_type)][VALIDATOR]
            if validator is not None:
                errors, placeholders = validator(
                    user_input, self._get_entry().runtime_data.rest
                )
            if not errors:
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
                "docs_url_jsonpath": DOCS_URL_JSONPATH,
                "docs_url_xml_convert_spec": DOCS_URL_XML_CONVERT_SPEC,
                "entry_title": self._get_entry().title,
            }
            | placeholders,
            errors=errors,
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
