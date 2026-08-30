"""Config flow for the LaCrosse integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BAUD,
    CONF_DATARATE,
    CONF_EXPIRE_AFTER,
    CONF_FREQUENCY,
    CONF_JEELINK_LED,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
    DEFAULT_BAUD,
    DEFAULT_DEVICE,
    DOMAIN,
    TYPES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        vol.Required(CONF_BAUD, default=DEFAULT_BAUD): cv.positive_int,
        vol.Optional(CONF_DATARATE): cv.positive_int,
        vol.Optional(CONF_FREQUENCY): cv.positive_int,
        vol.Optional(CONF_JEELINK_LED): cv.boolean,
        vol.Optional(CONF_TOGGLE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TOGGLE_MASK): cv.positive_int,
    }
)

STEP_SENSOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_TYPE): vol.In(TYPES),
        vol.Required(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    }
)


class LaCrosseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaCrosse."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._sensors: dict[str, dict[str, Any]] = {}

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml (sensor platform)."""
        _LOGGER.warning(
            "Importing LaCrosse from YAML is deprecated and will be removed"
        )
        entry_input: dict[str, Any] = {
            CONF_DEVICE: import_config[CONF_DEVICE],
            CONF_BAUD: import_config[CONF_BAUD],
            CONF_DATARATE: import_config.get(CONF_DATARATE),
            CONF_FREQUENCY: import_config.get(CONF_FREQUENCY),
            CONF_JEELINK_LED: import_config.get(CONF_JEELINK_LED),
            CONF_TOGGLE_INTERVAL: import_config.get(CONF_TOGGLE_INTERVAL),
            CONF_TOGGLE_MASK: import_config.get(CONF_TOGGLE_MASK),
        }
        sensors: dict[str, dict[str, Any]] = {}
        for slug, sensor_config in import_config.get(CONF_SENSORS, {}).items():
            sensor_input = dict(sensor_config)
            sensor_input[CONF_FRIENDLY_NAME] = sensor_input.pop(CONF_NAME, slug)
            sensor_key = sensor_input[CONF_FRIENDLY_NAME]
            sensors[sensor_key] = sensor_input
        entry_input[CONF_SENSORS] = sensors

        self._async_abort_entries_match({CONF_DEVICE: entry_input[CONF_DEVICE]})
        return self.async_create_entry(title=entry_input[CONF_DEVICE], data=entry_input)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial receiver configuration step."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            self._data = user_input
            return await self.async_step_sensor()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a sensor received by the configured receiver."""
        errors: dict[str, str] = {}

        if user_input is not None:
            sensor_key = f"{user_input[CONF_ID]}_{user_input[CONF_TYPE]}"
            if sensor_key in self._sensors:
                errors["base"] = "sensor_already_configured"
            else:
                self._sensors[sensor_key] = user_input
                return await self.async_step_add_sensor()

        return self.async_show_form(
            step_id="sensor",
            data_schema=STEP_SENSOR_DATA_SCHEMA,
            errors=errors or None,
        )

    async def async_step_add_sensor(self) -> ConfigFlowResult:
        """Offer to add another sensor or complete the flow."""
        return self.async_show_menu(
            step_id="add_sensor", menu_options=["sensor", "finish"]
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry using the configured receiver and sensors."""
        return self.async_create_entry(
            title=self._data[CONF_DEVICE],
            data={**self._data, CONF_SENSORS: self._sensors},
        )
