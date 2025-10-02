"""Config flow for the Template integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from functools import partial
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.update import UpdateDeviceClass
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
from homeassistant.data_entry_flow import section
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
    async_create_preview_alarm_control_panel,
)
from .binary_sensor import async_create_preview_binary_sensor
from .const import (
    CONF_ADVANCED_OPTIONS,
    CONF_AVAILABILITY,
    CONF_PRESS,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    DOMAIN,
)
from .cover import (
    CLOSE_ACTION,
    CONF_OPEN_AND_CLOSE,
    CONF_POSITION,
    OPEN_ACTION,
    POSITION_ACTION,
    STOP_ACTION,
    async_create_preview_cover,
)
from .event import CONF_EVENT_TYPE, CONF_EVENT_TYPES, async_create_preview_event
from .fan import (
    CONF_OFF_ACTION,
    CONF_ON_ACTION,
    CONF_PERCENTAGE,
    CONF_SET_PERCENTAGE_ACTION,
    CONF_SPEED_COUNT,
    async_create_preview_fan,
)
from .light import (
    CONF_HS,
    CONF_HS_ACTION,
    CONF_LEVEL,
    CONF_LEVEL_ACTION,
    CONF_TEMPERATURE,
    CONF_TEMPERATURE_ACTION,
    async_create_preview_light,
)
from .lock import CONF_LOCK, CONF_OPEN, CONF_UNLOCK, async_create_preview_lock
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
from .select import CONF_OPTIONS, CONF_SELECT_OPTION, async_create_preview_select
from .sensor import async_create_preview_sensor
from .switch import async_create_preview_switch
from .template_entity import TemplateEntity
from .update import (
    CONF_BACKUP,
    CONF_IN_PROGRESS,
    CONF_INSTALL,
    CONF_INSTALLED_VERSION,
    CONF_LATEST_VERSION,
    CONF_RELEASE_SUMMARY,
    CONF_RELEASE_URL,
    CONF_SPECIFIC_VERSION,
    CONF_TITLE,
    CONF_UPDATE_PERCENTAGE,
    async_create_preview_update,
)
from .vacuum import (
    CONF_FAN_SPEED,
    CONF_FAN_SPEED_LIST,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    async_create_preview_vacuum,
)

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

    if domain == Platform.COVER:
        schema |= _SCHEMA_STATE | {
            vol.Inclusive(OPEN_ACTION, CONF_OPEN_AND_CLOSE): selector.ActionSelector(),
            vol.Inclusive(CLOSE_ACTION, CONF_OPEN_AND_CLOSE): selector.ActionSelector(),
            vol.Optional(STOP_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_POSITION): selector.TemplateSelector(),
            vol.Optional(POSITION_ACTION): selector.ActionSelector(),
        }
        if flow_type == "config":
            schema |= {
                vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in CoverDeviceClass],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="cover_device_class",
                        sort=True,
                    ),
                )
            }

    if domain == Platform.EVENT:
        schema |= {
            vol.Required(CONF_EVENT_TYPE): selector.TemplateSelector(),
            vol.Required(CONF_EVENT_TYPES): selector.TemplateSelector(),
        }

        if flow_type == "config":
            schema |= {
                vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in EventDeviceClass],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="event_device_class",
                        sort=True,
                    ),
                )
            }

    if domain == Platform.FAN:
        schema |= _SCHEMA_STATE | {
            vol.Required(CONF_ON_ACTION): selector.ActionSelector(),
            vol.Required(CONF_OFF_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_PERCENTAGE): selector.TemplateSelector(),
            vol.Optional(CONF_SET_PERCENTAGE_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_SPEED_COUNT): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
                ),
            ),
        }

    if domain == Platform.IMAGE:
        schema |= {
            vol.Required(CONF_URL): selector.TemplateSelector(),
            vol.Optional(CONF_VERIFY_SSL, default=True): selector.BooleanSelector(),
        }

    if domain == Platform.LIGHT:
        schema |= _SCHEMA_STATE | {
            vol.Required(CONF_TURN_ON): selector.ActionSelector(),
            vol.Required(CONF_TURN_OFF): selector.ActionSelector(),
            vol.Optional(CONF_LEVEL): selector.TemplateSelector(),
            vol.Optional(CONF_LEVEL_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_HS): selector.TemplateSelector(),
            vol.Optional(CONF_HS_ACTION): selector.ActionSelector(),
            vol.Optional(CONF_TEMPERATURE): selector.TemplateSelector(),
            vol.Optional(CONF_TEMPERATURE_ACTION): selector.ActionSelector(),
        }

    if domain == Platform.LOCK:
        schema |= _SCHEMA_STATE | {
            vol.Required(CONF_LOCK): selector.ActionSelector(),
            vol.Required(CONF_UNLOCK): selector.ActionSelector(),
            vol.Optional(CONF_CODE_FORMAT): selector.TemplateSelector(),
            vol.Optional(CONF_OPEN): selector.ActionSelector(),
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

    if domain == Platform.UPDATE:
        schema |= {
            vol.Optional(CONF_INSTALLED_VERSION): selector.TemplateSelector(),
            vol.Optional(CONF_LATEST_VERSION): selector.TemplateSelector(),
            vol.Optional(CONF_INSTALL): selector.ActionSelector(),
            vol.Optional(CONF_IN_PROGRESS): selector.TemplateSelector(),
            vol.Optional(CONF_RELEASE_SUMMARY): selector.TemplateSelector(),
            vol.Optional(CONF_RELEASE_URL): selector.TemplateSelector(),
            vol.Optional(CONF_TITLE): selector.TemplateSelector(),
            vol.Optional(CONF_UPDATE_PERCENTAGE): selector.TemplateSelector(),
            vol.Optional(CONF_BACKUP): selector.BooleanSelector(),
            vol.Optional(CONF_SPECIFIC_VERSION): selector.BooleanSelector(),
        }
        if flow_type == "config":
            schema |= {
                vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in UpdateDeviceClass],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="update_device_class",
                        sort=True,
                    ),
                ),
            }

    if domain == Platform.VACUUM:
        schema |= _SCHEMA_STATE | {
            vol.Required(SERVICE_START): selector.ActionSelector(),
            vol.Optional(CONF_FAN_SPEED): selector.TemplateSelector(),
            vol.Optional(CONF_FAN_SPEED_LIST): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[],
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(SERVICE_SET_FAN_SPEED): selector.ActionSelector(),
            vol.Optional(SERVICE_STOP): selector.ActionSelector(),
            vol.Optional(SERVICE_PAUSE): selector.ActionSelector(),
            vol.Optional(SERVICE_RETURN_TO_BASE): selector.ActionSelector(),
            vol.Optional(SERVICE_CLEAN_SPOT): selector.ActionSelector(),
            vol.Optional(SERVICE_LOCATE): selector.ActionSelector(),
        }

    schema |= {
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
        vol.Optional(CONF_ADVANCED_OPTIONS): section(
            vol.Schema(
                {
                    vol.Optional(CONF_AVAILABILITY): selector.TemplateSelector(),
                }
            ),
            {"collapsed": True},
        ),
    }

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
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.EVENT,
    Platform.FAN,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.VACUUM,
]

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(TEMPLATE_TYPES, True),
    Platform.ALARM_CONTROL_PANEL: SchemaFlowFormStep(
        config_schema(Platform.ALARM_CONTROL_PANEL),
        preview="template",
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
    Platform.COVER: SchemaFlowFormStep(
        config_schema(Platform.COVER),
        preview="template",
        validate_user_input=validate_user_input(Platform.COVER),
    ),
    Platform.EVENT: SchemaFlowFormStep(
        config_schema(Platform.EVENT),
        preview="template",
        validate_user_input=validate_user_input(Platform.EVENT),
    ),
    Platform.FAN: SchemaFlowFormStep(
        config_schema(Platform.FAN),
        preview="template",
        validate_user_input=validate_user_input(Platform.FAN),
    ),
    Platform.IMAGE: SchemaFlowFormStep(
        config_schema(Platform.IMAGE),
        preview="template",
        validate_user_input=validate_user_input(Platform.IMAGE),
    ),
    Platform.LIGHT: SchemaFlowFormStep(
        config_schema(Platform.LIGHT),
        preview="template",
        validate_user_input=validate_user_input(Platform.LIGHT),
    ),
    Platform.LOCK: SchemaFlowFormStep(
        config_schema(Platform.LOCK),
        preview="template",
        validate_user_input=validate_user_input(Platform.LOCK),
    ),
    Platform.NUMBER: SchemaFlowFormStep(
        config_schema(Platform.NUMBER),
        preview="template",
        validate_user_input=validate_user_input(Platform.NUMBER),
    ),
    Platform.SELECT: SchemaFlowFormStep(
        config_schema(Platform.SELECT),
        preview="template",
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
    Platform.UPDATE: SchemaFlowFormStep(
        config_schema(Platform.UPDATE),
        preview="template",
        validate_user_input=validate_user_input(Platform.UPDATE),
    ),
    Platform.VACUUM: SchemaFlowFormStep(
        config_schema(Platform.VACUUM),
        preview="template",
        validate_user_input=validate_user_input(Platform.VACUUM),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.ALARM_CONTROL_PANEL: SchemaFlowFormStep(
        options_schema(Platform.ALARM_CONTROL_PANEL),
        preview="template",
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
    Platform.COVER: SchemaFlowFormStep(
        options_schema(Platform.COVER),
        preview="template",
        validate_user_input=validate_user_input(Platform.COVER),
    ),
    Platform.EVENT: SchemaFlowFormStep(
        options_schema(Platform.EVENT),
        preview="template",
        validate_user_input=validate_user_input(Platform.EVENT),
    ),
    Platform.FAN: SchemaFlowFormStep(
        options_schema(Platform.FAN),
        preview="template",
        validate_user_input=validate_user_input(Platform.FAN),
    ),
    Platform.IMAGE: SchemaFlowFormStep(
        options_schema(Platform.IMAGE),
        preview="template",
        validate_user_input=validate_user_input(Platform.IMAGE),
    ),
    Platform.LIGHT: SchemaFlowFormStep(
        options_schema(Platform.LIGHT),
        preview="template",
        validate_user_input=validate_user_input(Platform.LIGHT),
    ),
    Platform.LOCK: SchemaFlowFormStep(
        options_schema(Platform.LOCK),
        preview="template",
        validate_user_input=validate_user_input(Platform.LOCK),
    ),
    Platform.NUMBER: SchemaFlowFormStep(
        options_schema(Platform.NUMBER),
        preview="template",
        validate_user_input=validate_user_input(Platform.NUMBER),
    ),
    Platform.SELECT: SchemaFlowFormStep(
        options_schema(Platform.SELECT),
        preview="template",
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
    Platform.UPDATE: SchemaFlowFormStep(
        options_schema(Platform.UPDATE),
        preview="template",
        validate_user_input=validate_user_input(Platform.UPDATE),
    ),
    Platform.VACUUM: SchemaFlowFormStep(
        options_schema(Platform.VACUUM),
        preview="template",
        validate_user_input=validate_user_input(Platform.VACUUM),
    ),
}

CREATE_PREVIEW_ENTITY: dict[
    str,
    Callable[[HomeAssistant, str, dict[str, Any]], TemplateEntity],
] = {
    Platform.ALARM_CONTROL_PANEL: async_create_preview_alarm_control_panel,
    Platform.BINARY_SENSOR: async_create_preview_binary_sensor,
    Platform.COVER: async_create_preview_cover,
    Platform.EVENT: async_create_preview_event,
    Platform.FAN: async_create_preview_fan,
    Platform.LIGHT: async_create_preview_light,
    Platform.LOCK: async_create_preview_lock,
    Platform.NUMBER: async_create_preview_number,
    Platform.SELECT: async_create_preview_select,
    Platform.SENSOR: async_create_preview_sensor,
    Platform.SWITCH: async_create_preview_switch,
    Platform.UPDATE: async_create_preview_update,
    Platform.VACUUM: async_create_preview_vacuum,
}


class TemplateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for template helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

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

    config: dict = msg["user_input"]
    advanced_options = config.pop(CONF_ADVANCED_OPTIONS, {})
    preview_entity = CREATE_PREVIEW_ENTITY[template_type](
        hass, name, {**config, **advanced_options}
    )
    preview_entity.hass = hass
    preview_entity.registry_entry = entity_registry_entry

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = preview_entity.async_start_preview(
        async_preview_updated
    )
