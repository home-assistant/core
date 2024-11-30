"""Config flow for the Template integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from functools import partial
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .alarm_control_panel import (
    CONF_ARM_AWAY_ACTION,
    CONF_ARM_CUSTOM_BYPASS_ACTION,
    CONF_ARM_HOME_ACTION,
    CONF_ARM_NIGHT_ACTION,
    CONF_ARM_VACATION_ACTION,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_FORMAT,
    CONF_DISARM_ACTION,
    CONF_TRIGGER_ACTION,
    TemplateCodeFormat,
)
from .binary_sensor import async_create_preview_binary_sensor
from .const import CONF_PRESS, CONF_TURN_OFF, CONF_TURN_ON, DOMAIN
from .number import (
    CONF_MAX,
    CONF_MIN,
    CONF_SET_VALUE,
    CONF_STEP,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    async_create_preview_number,
)
from .select import CONF_OPTIONS, CONF_SELECT_OPTION
from .sensor import async_create_preview_sensor
from .switch import async_create_preview_switch
from .template_entity import TemplateEntity

_SCHEMA_STATE: dict[vol.Marker, Any] = {
    vol.Required(CONF_STATE): selector.TemplateSelector(),
}


def generate_schema(domain: str, flow_type: str) -> vol.Schema:
    """Generate schema."""
    schema: dict[vol.Marker, Any] = {}

    if flow_type == "config":
        schema = {vol.Required(CONF_NAME): selector.TextSelector()}

    if domain == Platform.ALARM_CONTROL_PANEL:
        schema |= {
            vol.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
            vol.Optional(CONF_DISARM_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_ARM_AWAY_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_ARM_CUSTOM_BYPASS_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_ARM_HOME_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_ARM_NIGHT_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_ARM_VACATION_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_TRIGGER_ACTION): selector.ActionSelector(),
            vol.Optional(
                CONF_CODE_ARM_REQUIRED, default=True
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CODE_FORMAT, default=TemplateCodeFormat.number.name
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[e.name for e in TemplateCodeFormat],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="alarm_control_panel_code_format",
                )
            ),
        }

    if domain == Platform.BINARY_SENSOR:
        schema |= _SCHEMA_STATE
        if flow_type == "config":
            schema |= {
                vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in BinarySensorDeviceClass],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="binary_sensor_device_class",
                        sort=True,
                    ),
                ),
            }

    if domain == Platform.BUTTON:
        schema |= {
            vol.Optional(CONF_PRESS): selector.ActionSelector(),
        }
        if flow_type == "config":
            schema |= {
                vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in ButtonDeviceClass],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="button_device_class",
                        sort=True,
                    ),
                )
            }

    if domain == Platform.IMAGE:
        schema |= {
            vol.Required(CONF_URL): selector.TemplateSelector(),
            vol.Optional(CONF_VERIFY_SSL, default=True): selector.BooleanSelector(),
        }

    if domain == Platform.NUMBER:
        schema |= {
            vol.Required(CONF_STATE): selector.TemplateSelector(),
            vol.Required(CONF_MIN, default=DEFAULT_MIN_VALUE): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(CONF_MAX, default=DEFAULT_MAX_VALUE): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(CONF_STEP, default=DEFAULT_STEP): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, multiline=False
                )
            ),
            vol.Required(CONF_SET_VALUE): selector.ActionSelector(),
        }

    if domain == Platform.SELECT:
        schema |= _SCHEMA_STATE | {
            vol.Required(CONF_OPTIONS): selector.TemplateSelector(),
            vol.Optional(CONF_SELECT_OPTION): selector.ActionSelector(),
        }

    if domain == Platform.SENSOR:
        schema |= _SCHEMA_STATE | {
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(
                        {
                            str(unit)
                            for units in DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        }
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_unit_of_measurement",
                    custom_value=True,
                    sort=True,
                ),
            ),
            vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        cls.value
                        for cls in SensorDeviceClass
                        if cls != SensorDeviceClass.ENUM
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_device_class",
                    sort=True,
                ),
            ),
            vol.Optional(CONF_STATE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[cls.value for cls in SensorStateClass],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_state_class",
                    sort=True,
                ),
            ),
        }

    if domain == Platform.SWITCH:
        schema |= {
            vol.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
            vol.Optional(CONF_TURN_ON): selector.ActionSelector(),
            vol.Optional(CONF_TURN_OFF): selector.ActionSelector(),
        }

    schema[vol.Optional(CONF_DEVICE_ID)] = selector.DeviceSelector()

    return vol.Schema(schema)


options_schema = partial(generate_schema, flow_type="options")

config_schema = partial(generate_schema, flow_type="config")


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to template_type."""
    return cast(str, options["template_type"])


def _validate_unit(options: dict[str, Any]) -> None:
    """Validate unit of measurement."""
    if (
        (device_class := options.get(CONF_DEVICE_CLASS))
        and (units := DEVICE_CLASS_UNITS.get(device_class)) is not None
        and (unit := options.get(CONF_UNIT_OF_MEASUREMENT)) not in units
    ):
        sorted_units = sorted(
            [f"'{unit!s}'" if unit else "no unit of measurement" for unit in units],
            key=str.casefold,
        )
        if len(sorted_units) == 1:
            units_string = sorted_units[0]
        else:
            units_string = f"one of {', '.join(sorted_units)}"

        raise vol.Invalid(
            f"'{unit}' is not a valid unit for device class '{device_class}'; "
            f"expected {units_string}"
        )


def _validate_state_class(options: dict[str, Any]) -> None:
    """Validate state class."""
    if (
        (state_class := options.get(CONF_STATE_CLASS))
        and (device_class := options.get(CONF_DEVICE_CLASS))
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

        raise vol.Invalid(
            f"'{state_class}' is not a valid state class for device class "
            f"'{device_class}'; expected {state_classes_string}"
        )


def validate_user_input(
    template_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Do post validation of user input.

    For sensors: Validate unit of measurement.
    For all domaines: Set template type.
    """

    async def _validate_user_input(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add template type to user input."""
        if template_type == Platform.SENSOR:
            _validate_unit(user_input)
            _validate_state_class(user_input)
        return {"template_type": template_type} | user_input

    return _validate_user_input


TEMPLATE_TYPES = [
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "image",
    "number",
    "select",
    "sensor",
    "switch",
]

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(TEMPLATE_TYPES),
    Platform.ALARM_CONTROL_PANEL: SchemaFlowFormStep(
        config_schema(Platform.ALARM_CONTROL_PANEL),
        validate_user_input=validate_user_input(Platform.ALARM_CONTROL_PANEL),
    ),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        config_schema(Platform.BINARY_SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.BINARY_SENSOR),
    ),
    Platform.BUTTON: SchemaFlowFormStep(
        config_schema(Platform.BUTTON),
        validate_user_input=validate_user_input(Platform.BUTTON),
    ),
    Platform.IMAGE: SchemaFlowFormStep(
        config_schema(Platform.IMAGE),
        validate_user_input=validate_user_input(Platform.IMAGE),
    ),
    Platform.NUMBER: SchemaFlowFormStep(
        config_schema(Platform.NUMBER),
        preview="template",
        validate_user_input=validate_user_input(Platform.NUMBER),
    ),
    Platform.SELECT: SchemaFlowFormStep(
        config_schema(Platform.SELECT),
        validate_user_input=validate_user_input(Platform.SELECT),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        config_schema(Platform.SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
    Platform.SWITCH: SchemaFlowFormStep(
        config_schema(Platform.SWITCH),
        preview="template",
        validate_user_input=validate_user_input(Platform.SWITCH),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.ALARM_CONTROL_PANEL: SchemaFlowFormStep(
        options_schema(Platform.ALARM_CONTROL_PANEL),
        validate_user_input=validate_user_input(Platform.ALARM_CONTROL_PANEL),
    ),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        options_schema(Platform.BINARY_SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.BINARY_SENSOR),
    ),
    Platform.BUTTON: SchemaFlowFormStep(
        options_schema(Platform.BUTTON),
        validate_user_input=validate_user_input(Platform.BUTTON),
    ),
    Platform.IMAGE: SchemaFlowFormStep(
        options_schema(Platform.IMAGE),
        validate_user_input=validate_user_input(Platform.IMAGE),
    ),
    Platform.NUMBER: SchemaFlowFormStep(
        options_schema(Platform.NUMBER),
        preview="template",
        validate_user_input=validate_user_input(Platform.NUMBER),
    ),
    Platform.SELECT: SchemaFlowFormStep(
        options_schema(Platform.SELECT),
        validate_user_input=validate_user_input(Platform.SELECT),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        options_schema(Platform.SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
    Platform.SWITCH: SchemaFlowFormStep(
        options_schema(Platform.SWITCH),
        preview="template",
        validate_user_input=validate_user_input(Platform.SWITCH),
    ),
}

CREATE_PREVIEW_ENTITY: dict[
    str,
    Callable[[HomeAssistant, str, dict[str, Any]], TemplateEntity],
] = {
    "binary_sensor": async_create_preview_binary_sensor,
    "number": async_create_preview_number,
    "sensor": async_create_preview_sensor,
    "switch": async_create_preview_switch,
}


class TemplateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for template helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "template/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a preview."""

    def _validate(schema: vol.Schema, domain: str, user_input: dict[str, Any]) -> Any:
        errors = {}
        key: vol.Marker
        for key, validator in schema.schema.items():
            if key.schema not in user_input:
                continue
            try:
                validator(user_input[key.schema])
            except vol.Invalid as ex:
                errors[key.schema] = str(ex.msg)

        if domain == Platform.SENSOR:
            try:
                _validate_unit(user_input)
            except vol.Invalid as ex:
                errors[CONF_UNIT_OF_MEASUREMENT] = str(ex.msg)
            try:
                _validate_state_class(user_input)
            except vol.Invalid as ex:
                errors[CONF_STATE_CLASS] = str(ex.msg)

        return errors

    entity_registry_entry: er.RegistryEntry | None = None
    if msg["flow_type"] == "config_flow":
        flow_status = hass.config_entries.flow.async_get(msg["flow_id"])
        template_type = flow_status["step_id"]
        form_step = cast(SchemaFlowFormStep, CONFIG_FLOW[template_type])
        schema = cast(vol.Schema, form_step.schema)
        name = msg["user_input"]["name"]
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError
        template_type = config_entry.options["template_type"]
        name = config_entry.options["name"]
        schema = cast(vol.Schema, OPTIONS_FLOW[template_type].schema)
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, flow_status["handler"]
        )
        if entries:
            entity_registry_entry = entries[0]

    errors = _validate(schema, template_type, msg["user_input"])

    @callback
    def async_preview_updated(
        state: str | None,
        attributes: Mapping[str, Any] | None,
        listeners: dict[str, bool | set[str]] | None,
        error: str | None,
    ) -> None:
        """Forward config entry state events to websocket."""
        if error is not None:
            connection.send_message(
                websocket_api.event_message(
                    msg["id"],
                    {"error": error},
                )
            )
            return
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {"attributes": attributes, "listeners": listeners, "state": state},
            )
        )

    if errors:
        connection.send_message(
            {
                "id": msg["id"],
                "type": websocket_api.TYPE_RESULT,
                "success": False,
                "error": {"code": "invalid_user_input", "message": errors},
            }
        )
        return

    preview_entity = CREATE_PREVIEW_ENTITY[template_type](hass, name, msg["user_input"])
    preview_entity.hass = hass
    preview_entity.registry_entry = entity_registry_entry

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = preview_entity.async_start_preview(
        async_preview_updated
    )
