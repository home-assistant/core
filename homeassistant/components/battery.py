"""
components.battery
~~~~~~~~~~~~~~~~~~~~~~~~~

battery:
  iphonebart:
    entity_id: device_tracker.iphonebart
    type: attribute
    attribute: battery
  vera:
    entity_id: vera.deviceid
    type: attribute
    attribute: battery_level
  mysensor:
    entity_id: sensor.mysensor
    type: state
"""

import logging
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_BATTERY_LEVEL

DEPENDENCIES = ['device_tracker']

# domain for the component
DOMAIN = 'battery'

# entity attributes
ATTR_STATUS = 'status'
ATTR_BATTERY_TYPE = 'battery type'
ATTR_ATTRIBUTE = 'attribute'

# default type
DEFAULT_TYPE = 'attribute'

# default attribute
DEFAULT_ATTRIBUTE = ATTR_BATTERY_LEVEL

# default unit_of_measurement
DEFAULT_UNIT = '%'

# default charged_level
DEFAULT_CHARGED = 100

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ get the battery details from configuration.yaml"""

    batteries = []
    if config.get(DOMAIN) is None:
        return False

    for bat, bat_config in config[DOMAIN].items():

        if not isinstance(bat_config, dict):
            _LOGGER.error("Missing configuration data for battery %s", bat)
            continue

        battery_type = bat_config.get('type', DEFAULT_TYPE)
        attribute = bat_config.get('attribute', DEFAULT_ATTRIBUTE)
        device_entity_id = bat_config.get('entity_id')
        unit_of_measurement = bat_config.get('unit_of_measurement',
                                             DEFAULT_UNIT)
        charged_level = bat_config.get('charged_level', DEFAULT_CHARGED)

        entity_id = DOMAIN + '.' + bat

        battery = Battery(hass, battery_type, attribute, device_entity_id,
                          unit_of_measurement, charged_level)
        battery.entity_id = entity_id

        battery.update_ha_state()
        battery.check_battery_state_change(None, None, None)

        batteries.append(battery)
        # main command to monitor battery of device
        track_state_change(hass, battery.device,
                           battery.check_battery_state_change)

    if not batteries:
        _LOGGER.error("No batteries added")
        return False

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Battery(Entity):  # pylint: disable=too-many-instance-attributes
    """ Represents a Battery in Home Assistant. """
    def __init__(self, hass, battery_type, attribute, device_entity_id,
                 unit_of_measurement, charged_level):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.device = device_entity_id
        self._battery_type = battery_type
        self._attribute = attribute
        self._batterylevel = 'not set'
        self._status = 'not set'
        self._unit_of_measurement = unit_of_measurement
        self._charged_level = charged_level

    @property
    def state(self):
        return self._batterylevel

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity """
        return self._unit_of_measurement

    @property
    def state_attributes(self):
        if self._battery_type == 'state':
            return {
                ATTR_STATUS: self._status,
                ATTR_BATTERY_TYPE: self._battery_type
            }
        elif self._battery_type == 'attribute':
            return {
                ATTR_STATUS: self._status,
                ATTR_BATTERY_TYPE: self._battery_type,
                ATTR_ATTRIBUTE: self._attribute
            }

    def check_battery_state_change(self, entity, old_state, new_state):
        # pylint: disable=too-many-branches
        """ Function to perform the battery checking for a device """
        if self._battery_type != 'attribute' and self._battery_type != 'state':
            return False

        if new_state is None:
            new_state = self.hass.states.get(self.device)

        if (new_state is None or
                ((self._battery_type == 'attribute') and
                 self._attribute not in new_state.attributes)):
            return

        if self._battery_type == 'attribute':
            currentbat = new_state.attributes.get(self._attribute)
        else:
            currentbat = new_state.state

        oldbat = None

        if (old_state is None or
                (old_state is not None and
                 (self._battery_type == 'attribute') and
                 self._attribute not in old_state.attributes)):
            oldbat = self._batterylevel
        elif (old_state is not None and (self._battery_type == 'attribute') and
              self._attribute in old_state.attributes):
            oldbat = old_state.attributes.get(self._attribute)
        elif old_state is not None and (self._battery_type == 'state'):
            oldbat = old_state.state

        if oldbat == 'not set':
            oldbat = None

        try:
            self._batterylevel = round(float(currentbat), 3)

            if (round(float(currentbat), 3) >=
                    round(float(self._charged_level), 3)):
                self._status = 'charged'
            elif oldbat is None:
                self._status = 'unknown'
            else:
                if round(float(currentbat), 3) > round(float(oldbat), 3):
                    self._status = 'charging'
                else:
                    self._status = 'in use'
        except ValueError:
            self._batterylevel = currentbat

        self.update_ha_state()
