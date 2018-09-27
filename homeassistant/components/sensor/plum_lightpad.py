"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.components.plum_lightpad import PLUM_DATA,\
    LOGICAL_LOAD_LOCATED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['plum_lightpad']
WATTS = 'Watts'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(hass, config, add_devices,
                               discovery_info=None):
    """Setup the Power Sensor support within Plum Lightpads."""
    plum = hass.data[PLUM_DATA]

    async def new_load(event):
        """Callback handler when a new logical load is discovered."""
        logical_load = plum.get_load(event.data['llid'])
        add_devices([
            PowerSensor(load=logical_load)
        ])

    hass.bus.async_listen(LOGICAL_LOAD_LOCATED, new_load)


class PowerSensor(Entity):
    """Representation of a Lightpad power meter Sensor."""

    def __init__(self, load):
        """Init Load (Power) sensor."""
        self._logical_load = load
        self._name = load.name
        self._power = load.power

        load.add_event_listener('power', self.power_event)

    def power_event(self, event):
        """Handler for power event updates."""
        self._power = event['watts']
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._power

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return WATTS
