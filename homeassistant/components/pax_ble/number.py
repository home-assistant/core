import logging

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory

from homeassistant.const import TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE

from .const import DOMAIN, CONF_NAME, CONF_MAC
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

# Writetype - Local will not send data to device (because it will be sent with some other value).
WT_REMOTE = 0
WT_LOCAL = 1

OPTIONS = {}
#OPTIONS['key'] = [MaxValue, MinValue, Step]
OPTIONS['fanspeed'] = [2400, 0, 1]
OPTIONS['boostmodespeed'] = [2400, 1000, 1]
OPTIONS['boostmodesec'] = [3600, 60, 1]
OPTIONS['hour'] = [23, 0, 1]
OPTIONS['min'] = [59, 0, 1]

class Sensor:
    def __init__(self, key, entityName, units, deviceClass, category, options, writeType):
        self.key = key
        self.entityName = entityName
        self.units = units
        self.deviceClass = deviceClass
        self.category = category
        self.options = options
        self.writeType = writeType

SENSOR_TYPES = [
    Sensor('fanspeed_humidity', 'Fanspeed Humidity', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('fanspeed_light', 'Fanspeed Light', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('fanspeed_trickle', 'Fanspeed Trickle', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('boostmodespeed', 'BoostMode Speed', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_LOCAL),
    Sensor('boostmodesec', 'BoostMode Time', 's', None, EntityCategory.CONFIG, OPTIONS['boostmodesec'], WT_LOCAL),
    Sensor('heatdistributorsettings_temperaturelimit', 'HeatDistributorSettings TemperatureLimit', TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('heatdistributorsettings_fanspeedbelow', 'HeatDistributorSettings FanSpeedBelow', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('heatdistributorsettings_fanspeedabove', 'HeatDistributorSettings FanSpeedAbove', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('silenthours_startinghour', 'SilentHours StartingHour', 'H', None, EntityCategory.CONFIG, OPTIONS['hour'], WT_REMOTE),
    Sensor('silenthours_startingminute', 'SilentHours StartingMinute', 'Min', None, EntityCategory.CONFIG, OPTIONS['min'], WT_REMOTE),
    Sensor('silenthours_endinghour', 'SilentHours EndingHour', 'H', None, EntityCategory.CONFIG, OPTIONS['hour'], WT_REMOTE),
    Sensor('silenthours_endingminute', 'SilentHours EndingMinute', 'Min', None, EntityCategory.CONFIG, OPTIONS['min'], WT_REMOTE),
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima numbers: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaNumberEntity(coordinator,sensor))
    async_add_devices(ha_entities, True)

class PaxCalimaNumberEntity(PaxCalimaEntity, NumberEntity):
    """Representation of a Number."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, sensor)

        """Number Entity properties"""
        self._attr_device_class = sensor.deviceClass
        self._attr_mode = "box"
        self._attr_native_max_value = sensor.options[0]
        self._attr_native_min_value = sensor.options[1]
        self._attr_native_step = sensor.options[2]
        self._attr_native_unit_of_measurement = sensor.units

        """Custom properties."""
        self._write_type = sensor.writeType

    @property
    def native_value(self):
        """ Return number value. """
        retVal = self.coordinator.get_data(self._key)
        
        try:
            retVal = int(retVal)
        except:
            pass
        
        return retVal

    async def async_set_native_value(self, value):
        if self._write_type == WT_LOCAL:
            self.coordinator.set_data(self._key, value)
        else: 
            """ Save old value """
            oldValue = self.coordinator.get_data(self._key)
                
            """ Write new value to our storage """
            self.coordinator.set_data(self._key, int(value))

            """ Write value to device """
            if not await self.coordinator.write_data(self._key):
                """ Restore value """
                self.coordinator.set_data(self._key, oldValue)
        self.async_schedule_update_ha_state()
