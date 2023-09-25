"""Constants for the Renson integration."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = "renson"

SET_TIMER_LEVEL_SCHEMA = vol.Schema(
    {
        vol.Required("timer_level"): vol.In(
            ["level1", "level2", "level3", "level4", "holiday", "breeze"]
        ),
        vol.Required("time"): cv.positive_int,
    }
)

SET_DAY_NIGHT_TIME_SCHEMA = vol.Schema(
    {
        vol.Required("day"): cv.time,
        vol.Required("night"): cv.time,
    }
)

SET_BREEZE_SCHEMA = vol.Schema(
    {
        vol.Required("breeze_level"): vol.In(["level1", "level2", "level3", "level4"]),
        vol.Required("temperature"): cv.positive_int,
        vol.Required("activate"): bool,
    }
)

SET_POLLUTION_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("day_pollution_level"): vol.In(
            ["level1", "level2", "level3", "level4"]
        ),
        vol.Required("night_pollution_level"): vol.In(
            ["level1", "level2", "level3", "level4"]
        ),
        vol.Optional("humidity_control"): bool,
        vol.Optional("airquality_control"): bool,
        vol.Optional("co2_control"): bool,
        vol.Optional("co2_threshold"): cv.positive_int,
        vol.Optional("co2_hysteresis"): cv.positive_int,
    }
)
