import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME, CONF_MAC
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

class Sensor:
    def __init__(self, key, entityName, category):
        self.key = key
        self.entityName = entityName
        self.category = category

SENSOR_TYPES = [
    Sensor('boostmode', 'BoostMode', None),
    Sensor('silenthours_on', 'SilentHours On', EntityCategory.CONFIG),
    Sensor('trickledays_weekdays', 'TrickleDays Weekdays', EntityCategory.CONFIG),
    Sensor('trickledays_weekends', 'TrickleDays Weekends', EntityCategory.CONFIG)    
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima switches: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaSwitchEntity(coordinator,sensor))
    async_add_devices(ha_entities, True)

class PaxCalimaSwitchEntity(PaxCalimaEntity, SwitchEntity):
    """Representation of a Command."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, sensor)
    
    @property
    def is_on(self):
        """Return the state of the switch."""
        return self.coordinator.get_data(self._key)
    
    async def async_turn_on(self, **kwargs):
        _LOGGER.debug('Enabling Boost Mode')
        await self.writeVal(1)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug('Disabling Boost Mode')
        await self.writeVal(0)

    async def writeVal(self, val):
        """ Write new value to our storage """ 
        self.coordinator.set_data(self._key, val)
        
        """ Write value to device """
        await self.coordinator.write_data(self._key)

        """ Update displayed value """
        self.async_schedule_update_ha_state()        
