"""Config flow for the LaCrosse integration."""

import logging
from typing import Any, override
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BATTERY,
    CONF_BAUD,
    CONF_DATARATE,
    CONF_EXPIRE_AFTER,
    CONF_FREQUENCY,
    CONF_HUMIDITY,
    CONF_JEELINK_LED,
    CONF_NEW_ID,
    CONF_TEMPERATURE,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
    DEFAULT_BAUD,
    DEFAULT_DEVICE,
    DOMAIN,
    LaCrosseSensorType,
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
        vol.Required(CONF_TEMPERATURE, default=True): cv.boolean,
        vol.Required(CONF_HUMIDITY, default=False): cv.boolean,
        vol.Required(CONF_BATTERY, default=False): cv.boolean,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    }
)

VALUE_SENSOR_TYPES = LaCrosseSensorType.TEMPERATURE | LaCrosseSensorType.HUMIDITY


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
            sensor_input[CONF_UNIQUE_ID] = uuid4().hex
            sensors[slug] = sensor_input
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the reconfiguration options of an existing receiver."""
        self._data = dict(self._get_reconfigure_entry().data)
        self._sensors = dict(self._data.pop(CONF_SENSORS, {}))
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["sensor", "change_id"]
        )

    async def async_step_change_id(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the ID of a sensor, which changes after a battery replacement."""
        errors: dict[str, str] = {}

        if user_input is not None:
            old_id = int(user_input[CONF_ID])
            new_id = user_input[CONF_NEW_ID]

            if any(
                sensor[CONF_ID] == new_id
                for sensor in self._sensors.values()
                if sensor[CONF_ID] != old_id
            ):
                errors["base"] = "sensor_already_configured"
            else:
                sensors: dict[str, dict[str, Any]] = {}
                for key, sensor in self._sensors.items():
                    if sensor[CONF_ID] != old_id:
                        sensors[key] = sensor
                        continue
                    sensors[f"{new_id}_{sensor[CONF_TYPE]}"] = {
                        **sensor,
                        CONF_ID: new_id,
                    }
                self._sensors = sensors
                self._async_update_device_identifiers(old_id, new_id)
                return await self.async_step_finish()

        sensor_ids = sorted(
            {str(sensor[CONF_ID]) for sensor in self._sensors.values()}, key=int
        )
        return self.async_show_form(
            step_id="change_id",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): SelectSelector(
                        SelectSelectorConfig(options=sensor_ids)
                    ),
                    vol.Required(CONF_NEW_ID): cv.positive_int,
                }
            ),
            errors=errors or None,
        )

    def _async_update_device_identifiers(self, old_id: int, new_id: int) -> None:
        """Move the device of a sensor to its new ID to keep its customizations."""
        receiver = self._data[CONF_DEVICE]
        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{receiver}_{old_id}"), self._get_reconfigure_entry().entry_id
        ):
            device_registry.async_update_device(
                device.id, new_identifiers={(DOMAIN, f"{receiver}_{new_id}")}
            )

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a sensor received by the configured receiver."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = LaCrosseSensorType(0)
            for sensor_type in LaCrosseSensorType:
                if user_input.pop(sensor_type.key):
                    selected |= sensor_type

            sensor_id = user_input[CONF_ID]
            keys = {
                sensor_type: f"{sensor_id}_{sensor_type.key}"
                for sensor_type in LaCrosseSensorType
                if sensor_type & selected
            }

            if not selected & VALUE_SENSOR_TYPES:
                errors["base"] = "value_type_required"
            elif any(key in self._sensors for key in keys.values()):
                errors["base"] = "sensor_already_configured"
            else:
                for sensor_type, key in keys.items():
                    self._sensors[key] = {
                        **user_input,
                        CONF_TYPE: sensor_type.key,
                        CONF_UNIQUE_ID: uuid4().hex,
                    }
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
        """Create or update an entry using the configured receiver and sensors."""
        data = {**self._data, CONF_SENSORS: self._sensors}
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return self.async_create_entry(title=self._data[CONF_DEVICE], data=data)
