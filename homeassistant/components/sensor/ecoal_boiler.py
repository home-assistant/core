from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ecoal sensors ."""
    from ..ecoal_boiler import g_ecoal_contr
    ## contr = ECoalControler("")

    add_devices([

            EcoalTempSensor(g_ecoal_contr,"Outside", 'outdoor_temp'),
            EcoalTempSensor(g_ecoal_contr,"Indoor", 'indoor_temp'),
            EcoalTempSensor(g_ecoal_contr,"Indoor 2", 'indoor2_temp'),

            EcoalTempSensor(g_ecoal_contr,"Domestic water", 'domestic_hot_water_temp'),
            EcoalTempSensor(g_ecoal_contr,"Domestic water target", 'target_domestic_hot_water_temp'),

            EcoalTempSensor(g_ecoal_contr,"Feedwater in", 'feedwater_in_temp'),
            EcoalTempSensor(g_ecoal_contr,"Feedwater out", 'feedwater_out_temp'),
            EcoalTempSensor(g_ecoal_contr,"Feedwater target", 'target_feedwater_temp'),

            EcoalTempSensor(g_ecoal_contr,"Fuel feeder", 'coal_feeder_temp'),
            EcoalTempSensor(g_ecoal_contr,"Exhaust gas", 'exhaust_temp'),
        ])



class EcoalTempSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, ecoal_contr, name, status_attr):
        """Initialize the sensor."""
        self._ecoal_contr = ecoal_contr
        self._name = name
        self._status_attr = status_attr
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        ## self._state = 23
        status = self._ecoal_contr.get_cached_status(0.5)  # Old values read 0.5 back can still be used
        self._state = getattr(status, self._status_attr)
