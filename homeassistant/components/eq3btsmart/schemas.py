"""Voluptuous schemas for eq3btsmart."""

from eq3btsmart.const import EQ3BT_MAX_TEMP, EQ3BT_MIN_TEMP, EQ3BT_OFF_TEMP
import voluptuous as vol

from homeassistant.const import CONF_MAC, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from .const import (
    CONF_ADAPTER,
    CONF_CURRENT_TEMP_SELECTOR,
    CONF_DEBUG_MODE,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_TARGET_TEMP_SELECTOR,
    Adapter,
    CurrentTemperatureSelector,
    TargetTemperatureSelector,
)


def times_and_temps_schema(value: dict):
    """Validate times."""

    def v_assert(value: bool, error: str):
        if not value:
            raise vol.Invalid(error)

    def time(i: int):
        return value.get(f"next_change_at_{i}")

    def temp(i: int):
        return value.get(f"target_temp_{i}")

    v_assert(temp(0), f"Missing target_temp_{0}")

    if time(0):
        v_assert(temp(1), f"Missing target_temp_{1} after: {time(0)}")

    for i in range(1, 7):
        if time(i):
            v_assert(time(i - 1), f"Missing next_change_at_{i-1} before: {time(i)}")
            v_assert(
                time(i - 1) < time(i),
                f"Times not in order at next_change_at_{i}: {time(i-1)}≥{time(i)}",
            )
            v_assert(temp(i + 1), f"Missing target_temp_{i+1} after: {time(i)}")

        if temp(i):
            v_assert(temp(i - 1), f"Missing target_temp_{i-1} before: {time(i-1)}")
            v_assert(time(i - 1), f"Missing next_change_at_{i-1} after: {time(i-2)}")

    return value


SCHEMA_TEMPERATURE = vol.Range(min=EQ3BT_MIN_TEMP, max=EQ3BT_MAX_TEMP)
SCHEMA_TIMES_AND_TEMPS = times_and_temps_schema
SCHEMA_SCHEDULE = {
    vol.Required("days"): cv.weekdays,
    vol.Required("target_temp_0"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_0"): cv.time,
    vol.Optional("target_temp_1"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_1"): cv.time,
    vol.Optional("target_temp_2"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_2"): cv.time,
    vol.Optional("target_temp_3"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_3"): cv.time,
    vol.Optional("target_temp_4"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_4"): cv.time,
    vol.Optional("target_temp_5"): SCHEMA_TEMPERATURE,
    vol.Optional("next_change_at_5"): cv.time,
    vol.Optional("target_temp_6"): SCHEMA_TEMPERATURE,
}
SCHEMA_SCHEDULE_SET = vol.Schema(
    vol.All(
        cv.make_entity_service_schema(SCHEMA_SCHEDULE),
        SCHEMA_TIMES_AND_TEMPS,
    )
)
SCHEMA_DEVICE = vol.Schema({vol.Required(CONF_MAC): cv.string})
SCHEMA_NAME_MAC = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): str,
    }
)


def schema_name(default_name: str):
    """Return name schema."""

    return vol.Schema({vol.Required(CONF_NAME, default=default_name): str})


SCHEMA_NAME = schema_name


def schema_options(
    suggested_scan_interval: int,
    suggested_current_temp_selector: CurrentTemperatureSelector,
    suggested_target_temp_selector: TargetTemperatureSelector,
    suggested_external_temp_sensor: str,
    suggested_adapter: Adapter,
    suggested_debug_mode: bool,
) -> vol.Schema:
    """Return options schema."""

    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                description={"suggested_value": suggested_scan_interval},
            ): cv.positive_float,
            vol.Required(
                CONF_CURRENT_TEMP_SELECTOR,
                description={"suggested_value": suggested_current_temp_selector},
            ): selector(
                {
                    "select": {
                        "options": [
                            {
                                "label": "nothing",
                                "value": CurrentTemperatureSelector.NOTHING,
                            },
                            {
                                "label": "target temperature to be set (fast)",
                                "value": CurrentTemperatureSelector.UI,
                            },
                            {
                                "label": "target temperature in device",
                                "value": CurrentTemperatureSelector.DEVICE,
                            },
                            {
                                "label": "valve based calculation",
                                "value": CurrentTemperatureSelector.VALVE,
                            },
                            {
                                "label": "external entity",
                                "value": CurrentTemperatureSelector.ENTITY,
                            },
                        ],
                    }
                }
            ),
            vol.Required(
                CONF_TARGET_TEMP_SELECTOR,
                description={"suggested_value": suggested_target_temp_selector},
            ): selector(
                {
                    "select": {
                        "options": [
                            {
                                "label": "target temperature to be set (fast)",
                                "value": TargetTemperatureSelector.TARGET,
                            },
                            {
                                "label": "target temperature in device",
                                "value": TargetTemperatureSelector.LAST_REPORTED,
                            },
                        ],
                    }
                }
            ),
            vol.Optional(
                CONF_EXTERNAL_TEMP_SENSOR,
                description={"suggested_value": suggested_external_temp_sensor},
            ): selector(
                {"entity": {"domain": "sensor", "device_class": "temperature"}}
            ),
            vol.Required(
                CONF_ADAPTER,
                description={"suggested_value": suggested_adapter},
            ): selector(
                {
                    "select": {
                        "options": [
                            {"label": "Automatic", "value": Adapter.AUTO},
                            {
                                "label": "Local adapters only",
                                "value": Adapter.LOCAL,
                            },
                            {
                                "label": "/org/bluez/hci0",
                                "value": "/org/bluez/hci0",
                            },
                            {
                                "label": "/org/bluez/hci1",
                                "value": "/org/bluez/hci1",
                            },
                            {
                                "label": "/org/bluez/hci2",
                                "value": "/org/bluez/hci2",
                            },
                            {
                                "label": "/org/bluez/hci3",
                                "value": "/org/bluez/hci3",
                            },
                        ],
                        "custom_value": True,
                    }
                }
            ),
            vol.Required(
                CONF_DEBUG_MODE,
                description={"suggested_value": suggested_debug_mode},
            ): cv.boolean,
        }
    )


SCHEMA_OPTIONS = schema_options

SCHEMA_SET_AWAY_UNTIL = cv.make_entity_service_schema(
    {
        vol.Required("away_until"): cv.datetime,
        vol.Required("temperature"): vol.Range(min=EQ3BT_OFF_TEMP, max=EQ3BT_MAX_TEMP),
    }
)
