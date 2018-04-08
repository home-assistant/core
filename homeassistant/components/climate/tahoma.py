"""
Support for Tahoma heatpump derogation.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.tahoma/
"""

from homeassistant.components.climate import (
    ClimateDevice,
    SUPPORT_AWAY_MODE)
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)
from homeassistant.const import TEMP_CELSIUS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tahoma controller devices."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['climate']:
        devices.append(TahomaClimate(device, controller))
    add_devices(devices, True)


class TahomaClimate(TahomaDevice, ClimateDevice):
    """Representation of a Tahoma heat pump derogration device."""

    def __init__(self, tahoma_device, controller):
        """Initialize the climate device."""
        super().__init__(tahoma_device, controller)
        if self.tahoma_device.type == \
           'io:EnergyConsumptionSensorsHeatPumpComponent':
            self._name = 'Heat pump derogation ('+self.name+')'
        self._support_flags = SUPPORT_AWAY_MODE
        self._away = tahoma_device.active_states['core:DerogationOnOffState'] \
            == "off"

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
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """No temperature handled here but this implementation is required."""
        return TEMP_CELSIUS

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.apply_action('setDerogationOnOffState', 'off')
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.apply_action('setDerogationOnOffState', 'on')
        self.schedule_update_ha_state()
