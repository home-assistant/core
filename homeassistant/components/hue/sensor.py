"""Hue sensor entities."""
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.components.hue.sensor_base import (
    GenericZLLSensor, async_setup_entry as shared_async_setup_entry)


LIGHT_LEVEL_NAME_FORMAT = "{} light level"
TEMPERATURE_NAME_FORMAT = "{} temperature"
BUTTON_EVENT_NAME_FORMAT = "{}"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    await shared_async_setup_entry(
        hass, config_entry, async_add_entities, binary=False)


class GenericHueGaugeSensorEntity(GenericZLLSensor, Entity):
    """Parent class for all 'gauge' Hue device sensors."""

    async def _async_update_ha_state(self, *args, **kwargs):
        await self.async_update_ha_state(self, *args, **kwargs)


class HueLightLevel(GenericHueGaugeSensorEntity):
    """The light level sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_ILLUMINANCE
    unit_of_measurement = "lx"

    @property
    def state(self):
        """Return the state of the device."""
        if self.sensor.lightlevel is None:
            return None

        # https://developers.meethue.com/develop/hue-api/supported-devices/#clip_zll_lightlevel
        # Light level in 10000 log10 (lux) +1 measured by sensor. Logarithm
        # scale used because the human eye adjusts to light levels and small
        # changes at low lux levels are more noticeable than at high lux
        # levels.
        return 10 ** ((self.sensor.lightlevel - 1) / 10000)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        attributes.update({
            "threshold_dark": self.sensor.tholddark,
            "threshold_offset": self.sensor.tholdoffset,
        })
        return attributes


class HueTemperature(GenericHueGaugeSensorEntity):
    """The temperature sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        if self.sensor.temperature is None:
            return None

        return self.sensor.temperature / 100
    
class HueSwitch(GenericHueGaugeSensorEntity):                                                  
    """The dimmer sensor entity for a Hue sensor device."""                                    
                                                 
    device_class = "switch"                             

    @property                                                          
    def state(self):                                                   
        BUTTONS = {                                                    
                    34: "1_click", 16: "2_click", 17: "3_click", 18: "4_click",
                    1000: "1_click", 2000: "2_click", 3000: "3_click", 4000: "4_click",
                    1001: "1_hold", 2001: "2_hold", 3001: "3_hold", 4001: "4_hold",    
                    1002: "1_click_up", 2002: "2_click_up", 3002: "3_click_up", 4002: "4_click_up",
                    1003: "1_hold_up", 2003: "2_hold_up", 3003: "3_hold_up", 4003: "4_hold_up",    
        }                                                                                          
        """Return the state of the device."""                                                      
        return BUTTONS[self.sensor.buttonevent]                                                    
                                                                                                   
    @property                                                                                      
    def icon(self) -> str:                                                                         
        """Icon to use in the frontend, if any."""                                                 
        return 'mdi:remote'                 
