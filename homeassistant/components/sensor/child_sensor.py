"""
homeassistant.components.sensor.child_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This component is designed to enable other components to create a sensor
component to monitor one of its state attributes without the nned to create
an entirely new sensor component.  This can be especially useful when
integrating with device that has several states you wish to monitor, eg. many
of my z-wave components are battery operated and it means a battery sensor can
easily be created for the component.


BASIC USAGE:

In order to create child sensors you need to use the "discovery" mechanism to
create multiple sensors on setup of another component.  The child sensor will
subscribe to the state change event of the parent entity and will monitor a
specified state attribute and use its value for its own state.

To implement you should add the following to your component:

from homeassistant.components.sensor import (
    DISCOVER_CHILD_SENSORS)

from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED)

...

// put this is the component class or setup_platform function

data = {}
data['name'] = 'Battery Level'
data['parent_entity_id'] = self.entity_id
data['watched_variable'] = 'batterylevel'
data['initial_state'] = 100
data['unit_of_measurement'] = '%'
data['state_attributes'] = {}
self._hass.bus.fire(
    EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
        ATTR_DISCOVERED: data})

This example will monitor the value of 'batterylevel' in the parent component's
'state.attributes' dictionary.  The state card will ned be visible on the UI
and available to automations etc.

'unit_of_measurement' is optional.
The 'state_attributes' is also optional but if a dictionary is passed in the
items will be added to the child sensors state attributes.

NOTES:

- At the moment this can only be created via the 'discovery' mechanism.  So do
not add it into your config file

- You need to add 'sensor' or 'child_sensor' as a dependency for your component
otherwise there is no guarantee this component will be loaded when the
discovery event fires.

"""

from homeassistant.helpers.entity import Entity

import logging

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """

    dev = []
    child_sensor = ChildSensor(config, discovery_info)
    dev.append(child_sensor)

    add_devices(dev)

    hass.states.track_change(
        discovery_info.get('parent_entity_id'), child_sensor.track_state)


class ChildSensor(Entity):
    """ A Child sensor """

    def __init__(self, config, discovery_info=None):
        self._name = discovery_info.get('name')
        self._parent_entity_id = discovery_info.get('parent_entity_id')
        self._state = discovery_info.get('initial_state')
        self._unit_of_measurement = discovery_info.get('unit_of_measurement')
        self._watched_variable = discovery_info.get('watched_variable')
        self._extra_state_attrs = discovery_info.get('state_attributes', {})

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def should_poll(self):
        """
        Polling is not required as state is updated from the parent
        """
        return False

    @property
    def state_attributes(self):
        attr = super().state_attributes
        attr['parent_device'] = self._parent_entity_id

        for key, value in self._extra_state_attrs.items():
            attr[key] = value

        return attr

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    def track_state(self, entity_id, old_state, new_state):
        if self._state != new_state:
            self._state = new_state.attributes.get(self._watched_variable)
            self.update_ha_state()

