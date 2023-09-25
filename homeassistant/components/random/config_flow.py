"""Config flow for Random helper."""
from collections.abc import Callable, Coroutine, Mapping
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

NONE_SENTINEL = "none"


def generate_schema(domain: str, flow_type: str) -> dict[vol.Marker, Any]:
    """Generate schema."""
    schema: dict[vol.Marker, Any] = {}

    if domain == Platform.BINARY_SENSOR and flow_type == "config":
        schema = {
            vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        NONE_SENTINEL,
                        *sorted(
                            [cls.value for cls in BinarySensorDeviceClass],
                            key=str.casefold,
                        ),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="binary_sensor_device_class",
                ),
            )
        }

    if domain == Platform.SENSOR:
        schema = {
            vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN): cv.positive_int,
            vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX): cv.positive_int,
            vol.Optional(CONF_DEVICE_CLASS, default=NONE_SENTINEL): SelectSelector(
                SelectSelectorConfig(
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
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_device_class",
                ),
            ),
            vol.Optional(
                CONF_UNIT_OF_MEASUREMENT, default=NONE_SENTINEL
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        NONE_SENTINEL,
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
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_unit_of_measurement",
                    custom_value=True,
                ),
            ),
        }

    return schema


def config_schema(domain: str) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
        }
        | generate_schema(domain, "config"),
    )


def _strip_sentinel(options: dict[str, Any]) -> None:
    """Convert sentinel to None."""
    for key in (CONF_DEVICE_CLASS, CONF_UNIT_OF_MEASUREMENT):
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
        sorted_units = sorted(
            [f"'{str(unit)}'" if unit else "no unit of measurement" for unit in units],
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

    For binary sensors: Strip none-sentinels.
    For sensors: Strip none-sentinels and validate unit of measurement.
    """

    async def _validate_user_input(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add template type to user input."""
        if template_type in (Platform.BINARY_SENSOR, Platform.SENSOR):
            _strip_sentinel(user_input)
        if template_type == Platform.SENSOR:
            _validate_unit(user_input)
        return {"entity_type": template_type} | user_input

    return _validate_user_input


RANDOM_TYPES = [
    "binary_sensor",
    "sensor",
]

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(RANDOM_TYPES),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        config_schema(Platform.BINARY_SENSOR),
        validate_user_input=validate_user_input(Platform.BINARY_SENSOR),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        config_schema(Platform.SENSOR),
        validate_user_input=validate_user_input(Platform.SENSOR),
    ),
}


class RandomConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for random helper."""

    config_flow = CONFIG_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
