"""Config flow for the Template integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import DOMAIN
from .sensor import async_create_preview_sensor
from .template_entity import TemplateEntity

NONE_SENTINEL = "none"


def generate_schema(domain: str) -> dict[vol.Marker, Any]:
    """Generate schema."""
    schema: dict[vol.Marker, Any] = {}

    if domain == Platform.SENSOR:
        schema = {
            vol.Optional(
                CONF_UNIT_OF_MEASUREMENT, default=NONE_SENTINEL
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        "none",
                        *sorted(
                            {
                                str(unit)
                                for units in DEVICE_CLASS_UNITS.values()
                                for unit in units
                                if unit is not None
                            },
                            key=str.casefold,
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_unit_of_measurement",
                    custom_value=True,
                ),
            ),
            vol.Optional(
                CONF_DEVICE_CLASS, default=NONE_SENTINEL
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        NONE_SENTINEL,
                        *sorted(
                            [
                                cls.value
                                for cls in SensorDeviceClass
                                if cls != SensorDeviceClass.ENUM
                            ],
                            key=str.casefold,
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_device_class",
                ),
            ),
            vol.Optional(
                CONF_STATE_CLASS, default=NONE_SENTINEL
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        NONE_SENTINEL,
                        *sorted([cls.value for cls in SensorStateClass]),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_state_class",
                ),
            ),
        }

    return schema


def options_schema(domain: str) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {vol.Required(CONF_STATE): selector.TemplateSelector()}
        | generate_schema(domain),
    )


def config_schema(domain: str) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_STATE): selector.TemplateSelector(),
        }
        | generate_schema(domain),
    )


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to template_type."""
    return cast(str, options["template_type"])


def _strip_sentinel(options: dict[str, Any]) -> None:
    """Convert sentinel to None."""
    for key in (CONF_DEVICE_CLASS, CONF_STATE_CLASS, CONF_UNIT_OF_MEASUREMENT):
        if key not in options:
            continue
        if options[key] == NONE_SENTINEL:
            options.pop(key)


def _validate_unit(options: dict[str, Any]) -> None:
    """Validate unit of measurement."""
    if (
        (device_class := options.get(CONF_DEVICE_CLASS))
        and (units := DEVICE_CLASS_UNITS.get(device_class)) is not None
        and (unit := options.get(CONF_UNIT_OF_MEASUREMENT)) not in units
    ):
        units_string = sorted(
            [str(unit) if unit else "no unit of measurement" for unit in units],
            key=str.casefold,
        )

        raise vol.Invalid(
            f"'{unit}' is not a valid unit for device class '{device_class}'; "
            f"expected one of {', '.join(units_string)}"
        )


def validate_user_input(
    template_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Do post validation of user input.

    For sensors: Strip none-sentinels and validate unit of measurement.
    For all domaines: Set template type.
    """

    async def _validate_user_input(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add template type to user input."""
        if template_type == Platform.SENSOR:
            _strip_sentinel(user_input)
            _validate_unit(user_input)
        return {"template_type": template_type} | user_input

    return _validate_user_input


TEMPLATE_TYPES = [
    "sensor",
]

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(TEMPLATE_TYPES),
    Platform.SENSOR: SchemaFlowFormStep(
        config_schema(Platform.SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.SENSOR: SchemaFlowFormStep(
        options_schema(Platform.SENSOR),
        preview="template",
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
}

CREATE_PREVIEW_ENTITY: dict[
    str,
    Callable[[HomeAssistant, str, dict[str, Any]], TemplateEntity],
] = {
    "sensor": async_create_preview_sensor,
}


class TemplateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for template helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

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
            _strip_sentinel(user_input)
            try:
                _validate_unit(user_input)
            except vol.Invalid as ex:
                errors[CONF_UNIT_OF_MEASUREMENT] = str(ex.msg)

        return errors

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

    errors = _validate(schema, template_type, msg["user_input"])

    @callback
    def async_preview_updated(
        state: str | None,
        attributes: Mapping[str, Any] | None,
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
                {"attributes": attributes, "state": state},
            )
        )

    if errors:
        connection.send_message(
            {
                "id": msg["id"],
                "type": websocket_api.const.TYPE_RESULT,
                "success": False,
                "error": {"code": "invalid_user_input", "message": errors},
            }
        )
        return

    _strip_sentinel(msg["user_input"])
    preview_entity = CREATE_PREVIEW_ENTITY[template_type](hass, name, msg["user_input"])
    preview_entity.hass = hass

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = preview_entity.async_start_preview(
        async_preview_updated
    )
