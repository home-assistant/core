"""Config flow for Random helper."""

from collections.abc import Callable, Coroutine, Mapping
from enum import StrEnum
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import DEVICE_CLASS_UNITS, SensorDeviceClass
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import DOMAIN
from .sensor import DEFAULT_MAX, DEFAULT_MIN


class _FlowType(StrEnum):
    CONFIG = "config"
    OPTION = "option"


def _generate_schema(domain: str, flow_type: _FlowType) -> vol.Schema:
    """Generate schema."""
    schema: dict[vol.Marker, Any] = {}

    if flow_type == _FlowType.CONFIG:
        schema[vol.Required(CONF_NAME)] = TextSelector()

        if domain == Platform.BINARY_SENSOR:
            schema[vol.Optional(CONF_DEVICE_CLASS)] = SelectSelector(
                SelectSelectorConfig(
                    options=[cls.value for cls in BinarySensorDeviceClass],
                    sort=True,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="binary_sensor_device_class",
                ),
            )

    if domain == Platform.SENSOR:
        schema.update(
            {
                vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN): cv.positive_int,
                vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX): cv.positive_int,
                vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            cls.value
                            for cls in SensorDeviceClass
                            if cls != SensorDeviceClass.ENUM
                        ],
                        sort=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="sensor_device_class",
                    ),
                ),
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            str(unit)
                            for units in DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        ],
                        sort=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="sensor_unit_of_measurement",
                        custom_value=True,
                    ),
                ),
            }
        )

    return vol.Schema(schema)


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to template_type."""
    return cast(str, options["entity_type"])


def _validate_unit(options: dict[str, Any]) -> None:
    """Validate unit of measurement."""
    if (
        (device_class := options.get(CONF_DEVICE_CLASS))
        and (units := DEVICE_CLASS_UNITS.get(device_class))
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


def validate_user_input(
    template_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Do post validation of user input.

    For sensors: Validate unit of measurement.
    """

    async def _validate_user_input(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add template type to user input."""
        if template_type == Platform.SENSOR:
            _validate_unit(user_input)
        return {"entity_type": template_type} | user_input

    return _validate_user_input


RANDOM_TYPES = [
    Platform.BINARY_SENSOR.value,
    Platform.SENSOR.value,
]

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(RANDOM_TYPES),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        _generate_schema(Platform.BINARY_SENSOR, _FlowType.CONFIG),
        validate_user_input=validate_user_input(Platform.BINARY_SENSOR),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        _generate_schema(Platform.SENSOR, _FlowType.CONFIG),
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        _generate_schema(Platform.BINARY_SENSOR, _FlowType.OPTION),
        validate_user_input=validate_user_input(Platform.BINARY_SENSOR),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        _generate_schema(Platform.SENSOR, _FlowType.OPTION),
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
}


class RandomConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for random helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
