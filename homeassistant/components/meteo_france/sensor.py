"""Support for Meteo-France raining forecast sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from . import ATTRIBUTION, CONF_CITY, DATA_METEO_FRANCE, SENSOR_TYPES
REQUIREMENTS = ['vigilancemeteo==2.0.0']

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_FORECAST = '1h rain forecast'
STATE_ATTR_BULLETIN_TIME = 'Date du bulletin'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Meteo-France sensor."""
    if discovery_info is None:
        return

    city = discovery_info[CONF_CITY]
    monitored_conditions = discovery_info[CONF_MONITORED_CONDITIONS]
    client = hass.data[DATA_METEO_FRANCE][city]

    from vigilancemeteo import ZoneAlerte

    if 'weather_alert' in monitored_conditions:
        # TODO: add link with client to retrieve the area code and pass it to ZoneAlerte
        alert_watcher = ZoneAlerte('02')
    else:
        alert_watcher = None

    add_entities([MeteoFranceSensor(variable, client, alert_watcher)
                  for variable in monitored_conditions], True)


class MeteoFranceSensor(Entity):
    """Representation of a Meteo-France sensor."""

    def __init__(self, condition, client, alert_watcher):
        """Initialize the Meteo-France sensor."""
        self._condition = condition
        self._client = client
        self._alert_watcher = alert_watcher
        self._state = None
        self._data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(
            self._data['name'], SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._condition == 'next_rain' and 'rain_forecast' in self._data:
            return {
                **{STATE_ATTR_FORECAST: self._data['rain_forecast']},
                ** self._data['next_rain_intervals'],
                **{ATTR_ATTRIBUTION: ATTRIBUTION}
            }
        elif self._condition == 'weather_alert':
            from vigilancemeteo import ZoneAlerte

            alert_type_list = {}
            # Create one attribute for each weather alert type.
            for alert_type in ZoneAlerte.LISTE_TYPE_ALERTE:
                if alert_type in self._alert_watcher.liste_alertes:
                    alert_type_list[alert_type] = self._alert_watcher.liste_alertes[alert_type]
                else:
                    alert_type_list[alert_type] = 'Vert'

            return {
                **{STATE_ATTR_BULLETIN_TIME: self._alert_watcher.date_mise_a_jour},
                ** alert_type_list,
                ATTR_ATTRIBUTION: ATTRIBUTION
            }

        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._client.update()
            self._data = self._client.get_data()

            if self._condition == 'weather_alert':
                self._alert_watcher.mise_a_jour_etat()
                self._state = self._alert_watcher.synthese_couleur
                return
            else:
                self._state = self._data[self._condition]
        except KeyError: # TODO: catch weather alert error ?
            _LOGGER.error("No condition %s for location %s",
                          self._condition, self._data['name'])
            self._state = None
