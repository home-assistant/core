"""
Allows to configure ecoal (esterownik.pl) solid fuel boiler controller as set of switches operating over pumps
Example configuration:

switch:
  - platform: ecoal_boiler
    enable:
      central_heating_pump: Wall radiators
      central_heating_pump2: Floor radiators
      # domestic_hot_water_pump: N/A

ecoal_boiler:
  host: 192.168.1.123
  login: admin
  password: admin


sets names for two pumps (central_heating_pump,central_heating_pump2).
Missing grom config 3rd pump ( domestic_hot_water_pump ) is not used

"""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Available ids
PUMP_IDNAMES = ('central_heating_pump', 'domestic_hot_water_pump', 'central_heating_pump2', )

ENABLED_SCHEMA = {}
for pump_id in PUMP_IDNAMES:
    ENABLED_SCHEMA[vol.Optional(pump_id)] = cv.string
CONF_ENABLE = 'enable'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENABLE): ENABLED_SCHEMA,
})



def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up switches based on ecoal interface."""
    from ..ecoal_boiler import g_ecoal_contr

    ## invert_logic = config.get(CONF_INVERT_LOGIC)

    config_enable = config.get(CONF_ENABLE, {})
    #_LOGGER.debug("config_enable: %r", config_enable)
    switches = []
    for pump_id in PUMP_IDNAMES:
        name = config_enable.get(pump_id)
        if name:
            switches.append(EcoalSwitch(g_ecoal_contr, name, pump_id))
    add_entities(switches)


class EcoalSwitch(ToggleEntity):
    """Representation of Ecoal switch."""

    def __init__(self, ecoal_contr, name, state_attr):
        """Initialize switch"""
        self._ecoal_contr = ecoal_contr
        self._name = name
        self._state_attr = state_attr
        # NOTE: Convetion set_<attr> and status.<attr> is held inside ecoal_boiler.http_interface
        self._contr_set_fun = getattr(self._ecoal_contr, 'set_'+state_attr)
        # No setting value, read instead
        self._state = self.is_on


    @property
    def name(self) -> Optional[str] :
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        status = self._ecoal_contr.get_cached_status(max_cache_period=1)
        self._state = getattr(status, self._state_attr)
        ## self._state = bool(status.domestic_hot_water_pump)
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the device on."""
        # self._ecoal_contr.set_domestic_hot_water_pump(1)
        self._contr_set_fun(1)
        # Reread state without using cache here
        self._ecoal_contr.get_status()
        self.is_on
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        ## self._ecoal_contr.set_domestic_hot_water_pump(0)
        self._contr_set_fun(0)
        # Reread state without using cache here
        self._ecoal_contr.get_status()
        self.is_on
        self.schedule_update_ha_state()

