"""Support for dobiss climate control."""
import logging

from dobissapi import DobissTempSensor
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity

from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    UnitOfTemperature,
)
from homeassistant.helpers.config_validation import entity_id

from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_HVAC_TEMP_TIMER = "set_hvac_temp_timer"

SET_HVAC_TEMP_TIMER_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_ENTITY_ID): vol.Coerce(entity_id),
            vol.Optional(ATTR_TIME): vol.Coerce(int),
            vol.Optional(ATTR_TEMPERATURE): vol.Coerce(float),
        }
    )
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobisssensor."""

    _LOGGER.debug(f"Setting up climate component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    # only add HVAC objects for temperature sensors when there is at least a schedule entry
    if len(dobiss.calendars) == 0:
        return

    entities = []
    d_entities = dobiss.get_devices_by_type(DobissTempSensor)
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        entities.append(HADobissClimateControl(d))
    if entities:
        async_add_entities(entities)

    async def handle_set_hvac_temp_timer(call):
        """Handle set_hvac_timer service."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        entity = next(
            (dev for dev in entities if dev.entity_id == entity_id),
            None,
        )
        if entity is None:
            raise ValueError(f"no entity found in {DOMAIN} that matches {entity_id}")
        time = call.data.get(ATTR_TIME, None)
        temp = call.data.get(ATTR_TEMPERATURE, entity._dobisssensor.asked)
        await entity._dobisssensor.set_temp_timer(temp, time)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HVAC_TEMP_TIMER,
        handle_set_hvac_temp_timer,
        schema=SET_HVAC_TEMP_TIMER_SCHEMA,
    )


class HADobissClimateControl(ClimateEntity):
    """Dobiss ssensor device."""

    should_poll = False

    temperature_unit = UnitOfTemperature.CELSIUS

    supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

    def __init__(self, dobisssensor: DobissTempSensor):
        """Init dobiss ClimateControl device."""
        super().__init__()
        self._dobisssensor = dobisssensor

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, f"climatecontrol_{self._dobisssensor.object_id}")},
            "name": f"climatecontrol_{self.name}",
            "manufacturer": "dobiss",
        }

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        return self._dobisssensor.attributes

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobisssensor.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobisssensor.remove_callback(self.async_write_ha_state)

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._dobisssensor.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"climatecontrol_{self._dobisssensor.object_id}"

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._dobisssensor.value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._dobisssensor.asked

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.1

    async def async_set_temperature(self, **kwargs):
        value = kwargs.get(ATTR_TEMPERATURE, self.target_temperature)
        await self._dobisssensor.set_temperature(value)

    async def async_set_hvac_mode(self, hvac_mode: str):
        await self._dobisssensor.set_manual_mode(hvac_mode == HVACMode.HEAT)

    async def async_set_preset_mode(self, preset_mode: str):
        await self._dobisssensor.set_preset_mode(preset_mode)

    @property
    def preset_modes(self):
        return self._dobisssensor._dobiss.calendars

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.
        Requires ClimateEntityFeature.
        """
        return self._dobisssensor.calendar

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVACMode.
        """
        if self._dobisssensor.time is not None and self._dobisssensor.time >= 0:
            return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.
        Need to be a subset of HVACMode.
        """
        modes = []
        modes.append(HVACMode.HEAT)
        modes.append(HVACMode.AUTO)
        return modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.
        Need to be one of HVACAction.
        """
        if self._dobisssensor.status == 1:
            return HVACAction.HEATING
        return HVACAction.IDLE
