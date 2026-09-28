"""Config Flow for the RESTful integration."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from types import MethodType
from typing import Any, cast, override
from xml.parsers.expat import ExpatError

import probatio

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PAYLOAD,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.template import Template

from . import CONFIG_ENTRY_PLATFORMS, create_rest_data_from_config_entry
from .const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    DEFAULT_BINARY_SENSOR_NAME,
    DEFAULT_SENSOR_NAME,
    DOCS_URL_AVAILABILITY,
    DOCS_URL_JSONPATH,
    DOCS_URL_RESTFUL_SENSOR_FORCE_UPDATE,
    DOCS_URL_TEMPLATE_DATA_PROCESSING,
    DOCS_URL_XML_CONVERT_SPEC,
    DOMAIN,
)
from .coordinator import RestConfigEntry
from .data import RestData
from .schema import (
    BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
    RESOURCE_FLOW_SCHEMA,
    SENSOR_SUBENTRY_FLOW_SCHEMA,
)
from .util import parse_json_attributes_raise_error

NO_PLATFORM = "none"


MATCH_ON = {
    CONF_RESOURCE,
    CONF_METHOD,
    CONF_PAYLOAD,
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_PARAMS,
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
            self._async_abort_entries_match(
                {key: value for key, value in user_input.items() if key in MATCH_ON}
            )
            try:
                rest = create_rest_data_from_config_entry(self.hass, user_input)
                await rest.async_update()
                if rest.last_exception:
                    errors["base"] = (
                        "endpoint_error"
                        if not isinstance(rest.last_exception, TimeoutError)
                        else "timeout_error"
                    )
                    placeholders["endpoint_error_message"] = str(rest.last_exception)
                if not errors:
                    self._title = f"{user_input[CONF_METHOD]} {Template(user_input[CONF_RESOURCE], self.hass).async_render()}"
                    self._data = user_input
                    return await self.async_step_subentries_menu()
            except TemplateError as exc:
                errors["base"] = "template_error"
                placeholders["template_error_message"] = str(exc)
            except UnicodeDecodeError as exc:
                errors[CONF_ENCODING] = "decoding_error"
                placeholders["decoding_error_message"] = str(exc)
        suggested_values = user_input or {}
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
            last_step=False,
        )

    async def async_step_subentries_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show menu for subentry creation."""

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

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return dict.fromkeys(CONFIG_ENTRY_PLATFORMS, RestSubentryFlow)


def _validate_unit(data: dict[str, Any]) -> dict[str, Any]:
    """Validate unit of measurement, from template config_flow.py."""
    if (
        (device_class := data.get(CONF_DEVICE_CLASS))
        and (units := DEVICE_CLASS_UNITS.get(device_class)) is not None
        and (unit := data.get(CONF_UNIT_OF_MEASUREMENT)) not in units
    ):
        # Sort twice to make sure strings with same case-insensitive order of
        # letters are sorted consistently still.
        sorted_units = sorted(
            sorted(
                [f"'{unit!s}'" if unit else "no unit of measurement" for unit in units],
            ),
            key=str.casefold,
        )
        if len(sorted_units) == 1:
            units_string = sorted_units[0]
        else:
            units_string = f"one of {', '.join(sorted_units)}"

        raise probatio.Invalid(
            translation_key=(
                "unit_validation_error" if unit is not None else "unit_required_error"
            ),
            placeholders={
                "unit": unit,
                "device_class": device_class,
                "units_string": units_string,
            },
            path=[CONF_UNIT_OF_MEASUREMENT],
        )
    return data


def _validate_state_class(data: dict[str, Any]) -> dict[str, Any]:
    """Validate state class. From template config_flow.py."""
    if (
        (state_class := data.get(CONF_STATE_CLASS))
        and (device_class := data.get(CONF_DEVICE_CLASS))
        and (state_classes := DEVICE_CLASS_STATE_CLASSES.get(device_class)) is not None
        and state_class not in state_classes
    ):
        sorted_state_classes = sorted(
            [f"'{state_class!s}'" for state_class in state_classes],
            key=str.casefold,
        )
        if len(sorted_state_classes) == 0:
            state_classes_string = "no state class"
        elif len(sorted_state_classes) == 1:
            state_classes_string = sorted_state_classes[0]
        else:
            state_classes_string = f"one of {', '.join(sorted_state_classes)}"

        raise probatio.Invalid(
            translation_key="state_class_validation_error",
            placeholders={
                "state_class": state_class,
                "device_class": device_class,
                "state_classes_string": state_classes_string,
            },
            path=[CONF_STATE_CLASS],
        )
    return data


def _validate_sensor_rest_data(rest: RestData) -> Callable[[Any], Any]:
    """Parameterized validator for sensor_input."""

    def check_data(data: dict[str, Any]) -> dict[str, Any]:
        if data.get(CONF_JSON_ATTRS):
            attrs = [item["item"] for item in data[CONF_JSON_ATTRS]]
            try:
                parse_json_attributes_raise_error(
                    rest.data_without_xml(), attrs, data.get(CONF_JSON_ATTRS_PATH)
                )
            except HomeAssistantError as exc:
                if exc.translation_key is not None:
                    raise probatio.Invalid(
                        translation_key=exc.translation_key,
                        placeholders=exc.translation_placeholders,
                    ) from exc
            except ExpatError as exc:
                raise probatio.Invalid(
                    translation_key="xml_parse_error",
                    placeholders={"xml_parse_error_message": str(exc)},
                ) from exc

        return data

    return check_data


@dataclass
class SubentryConfig:
    """Class to hold subentry config helpers/validators."""

    default_name: str
    flow_schema: probatio.Schema
    post_schema_validation: (
        Callable[[RestData], probatio.Schema] | probatio.Schema | None
    ) = None


SUBENTRY_CONFIG: dict[Platform, SubentryConfig] = {
    Platform.BINARY_SENSOR: SubentryConfig(
        default_name=DEFAULT_BINARY_SENSOR_NAME,
        flow_schema=BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA,
    ),
    Platform.SENSOR: SubentryConfig(
        default_name=DEFAULT_SENSOR_NAME,
        flow_schema=SENSOR_SUBENTRY_FLOW_SCHEMA,
        post_schema_validation=lambda data: probatio.Schema(
            probatio.All(
                _validate_unit, _validate_state_class, _validate_sensor_rest_data(data)
            )
        ),
    ),
}


class RestSubentryFlow(ConfigSubentryFlow):
    """Base class for subentry flows."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Base step user."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        entry: RestConfigEntry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="config_entry_not_loaded")
        if user_input is not None:
            if schema_validator := SUBENTRY_CONFIG[
                Platform(self._subentry_type)
            ].post_schema_validation:
                if callable(schema_validator):
                    if len(entry.subentries) == 0:
                        await entry.runtime_data.async_refresh()
                        if entry.runtime_data.rest.data is not None:
                            schema_validator = schema_validator(entry.runtime_data.rest)
                        else:
                            ex = cast(
                                HomeAssistantError,
                                entry.runtime_data.last_exception,
                            )
                            errors["base"] = ex.translation_key or "endpoint_error"
                            placeholders = placeholders | (
                                ex.translation_placeholders
                                or {"endpoint_error_message": str(ex)}
                            )
                if isinstance(schema_validator, probatio.Schema):
                    try:
                        schema_validator(user_input)
                    except probatio.Invalid as exc:
                        for error in (
                            [exc]
                            if not isinstance(exc, probatio.MultipleInvalid)
                            else exc.errors
                        ):
                            path = error.path[0] if error.path else "base"
                            errors[path] = exc.translation_key or str(exc)
                            placeholders.update(exc.placeholders)
            if not errors:
                title: str = user_input.get(
                    CONF_NAME,
                    SUBENTRY_CONFIG[Platform(self._subentry_type)].default_name,
                )
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                    unique_id=f"{self._subentry_type}_{self.flow_id}",
                )
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "docs_url_availability": DOCS_URL_AVAILABILITY,
                "docs_url_restful_sensor_force_update": DOCS_URL_RESTFUL_SENSOR_FORCE_UPDATE,
                "docs_url_template_data_processing": DOCS_URL_TEMPLATE_DATA_PROCESSING,
                "docs_url_jsonpath": DOCS_URL_JSONPATH,
                "docs_url_xml_convert_spec": DOCS_URL_XML_CONVERT_SPEC,
                "entry_title": self._get_entry().title,
            }
            | placeholders,
            errors=errors,
            data_schema=(
                self.add_suggested_values_to_schema(
                    SUBENTRY_CONFIG[Platform(self._subentry_type)].flow_schema,
                    user_input or {},
                )
            ),
            last_step=True,
        )
