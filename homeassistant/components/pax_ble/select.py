import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME, CONF_MAC
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

class Sensor:
    def __init__(self, key, entityName, category, options):
        self.key = key
        self.entityName = entityName
        self.category = category
        self.options = options

# Creating nested dictionary of key/pairs
OPTIONS = {
    'automatic_cycles': {'0': "Off", '1': "30 min", '2': "60 min", '3': "90 min"},
    'lightsensorsettings_delayedstart': {'0': "No delay", '5': "5 min", '10': "10 min"},
    'lightsensorsettings_runningtime': {'5': "5 min", '10': "10 min", '15': "15 min", '30': "30 min", '60': "60 min"},
    'sensitivity': {'0': "Off", '1': "Low sensitivity", '2': "Medium sensitivity", '3': "High sensitivity"}
}

SENSOR_TYPES = [
    Sensor('automatic_cycles', 'Automatic Cycles', EntityCategory.CONFIG, OPTIONS['automatic_cycles']),
    Sensor('lightsensorsettings_delayedstart', 'LightSensorSettings DelayedStart', EntityCategory.CONFIG, OPTIONS['lightsensorsettings_delayedstart']),
    Sensor('lightsensorsettings_runningtime', 'LightSensorSettings Runningtime', EntityCategory.CONFIG, OPTIONS['lightsensorsettings_runningtime']),
    Sensor('sensitivity_humidity', 'Sensitivity Humidity', EntityCategory.CONFIG, OPTIONS['sensitivity']),
    Sensor('sensitivity_light', 'Sensitivity Light', EntityCategory.CONFIG, OPTIONS['sensitivity'])
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup selects from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima selects: %s", config_entry.data[CONF_NAME])
    
    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaSelectEntity(coordinator,sensor)) 
    async_add_devices(ha_entities, True)

class PaxCalimaSelectEntity(PaxCalimaEntity, SelectEntity):
    """Representation of a Select."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, sensor)

        """Select Entity properties"""    
        self._options = sensor.options

    @property
    def current_option(self):
        try:
            optionIndexStr = self.coordinator.get_data(self._key)
            option = self._options[str(optionIndexStr)]
        except Exception as e:            
            option = "Unknown"
        return option

    @property
    def options(self):
        return list(self._options.values())

    async def async_select_option(self, option):
        """ Save old value """
        oldValue = self.coordinator.get_data(self._key)
        
        """ Find new value """ 
        value = None
        for key, val in self._options.items():
            if val == option:
                value = key
                break

        if value is None:
            return
        
        """ Write new value to our storage """ 
        self.coordinator.set_data(self._key, value)
        
        """ Write value to device """
        ret = await self.coordinator.write_data(self._key)
        
        """ Update HA value """
        if not ret:
            """ Restore value """
            self.coordinator.set_data(self._key, oldValue)
        self.async_schedule_update_ha_state()
