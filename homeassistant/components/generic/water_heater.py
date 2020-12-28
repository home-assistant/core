"""Support for generic water heater units."""
import logging

import voluptuous as vol

from homeassistant.components.water_heater import (
    PLATFORM_SCHEMA,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
DEFAULT_NAME = "Generic Water Heater"

CONF_HEATER = "heater"
CONF_SENSOR = "target_sensor"
CONF_TARGET_TEMP = "target_temperature"
CONF_TEMP_DELTA = "delta_temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TEMP_DELTA): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the generic water_heater devices."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    target_temp = config.get(CONF_TARGET_TEMP)
    temp_delta = config.get(CONF_TARGET_TEMP)
    unit = hass.config.units.temperature_unit

    async_add_entities(
        [
            GenericWaterHeater(
                name, heater_entity_id, sensor_entity_id, target_temp, temp_delta, unit
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the generic config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class GenericWaterHeater(WaterHeaterEntity, RestoreEntity):
    """Representation of a generic water_heater device."""

    def __init__(
        self, name, heater_entity_id, sensor_entity_id, target_temp, temp_delta, unit
    ):
        """Initialize the water_heater device."""
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self._support_flags = SUPPORT_FLAGS_HEATER
        self._target_temperature = target_temp
        self._temperature_delta = temp_delta
        self._unit_of_measurement = unit
        self._current_operation = STATE_ON
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. on, off."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._async_control_heating()
        self.schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._current_operation = operation_mode
        await self._async_control_heating()
        self.schedule_update_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._cur_temp = float(new_state.state)
        await self._async_control_heating()
        self.async_write_ha_state()

    @callback
    def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.state == STATE_ON and self._current_operation == STATE_OFF:
            self._current_operation = new_state.state
            self.async_write_ha_state()

    async def _async_control_heating(self, time=None):
        """Check if we need to turn heating on or off."""
        if self._current_operation == STATE_OFF:
            return

        if self._cur_temp < self._target_temperature - self._temperature_delta:
            _LOGGER.info("Turning on heater %s", self.heater_entity_id)
            await self._async_heater_turn_on()
        else:
            _LOGGER.info("Turning off heater %s", self.heater_entity_id)
            await self._async_heater_turn_off()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.sensor_entity_id], self._async_sensor_changed
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.heater_entity_id], self._async_switch_changed
            )
        )

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._target_temperature = float(old_state.attributes.get(ATTR_TEMPERATURE))
        else:
            # Default to current temperature
            self._target_temperature = None

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        )

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )
