"""Support for JLR InControl sensors"""
import logging

from . import JLREntity, RESOURCES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the JLR sensors."""
    if discovery_info is None:
        return
    add_entities([JLRSensor(hass, *discovery_info)])


class JLRSensor(JLREntity):
    """Representation of a JLR Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.info('Getting state of %s sensor' % self._attribute)

        val = self._get_vehicle_status(self.vehicle.info.get('vehicleStatus'))
        if val is None:
            return val
        if val:
            val = val[self._attribute]
        else:
            return None

        if self._attribute in ['last_connected', 'service_inspection', 'oil_inspection']:
            return str(val)
        if self._attribute in ['ODOMETER_METER']:
            return float(int(val) / 1000)
        else:
            return int(float(val))

    def _get_vehicle_status(self, vehicle):
        dict_only = {}
        for el in vehicle:
            dict_only[el.get('key')] = el.get('value')
        return dict_only

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return RESOURCES[self._attribute][3]

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]

    @property
    def available(self):
        """Return True if entity is available."""
        return True

    # def update(self):
    #     _LOGGER.info("UPDATING")
    #     vehicle_status = self.vehicle.get_status().get('vehicleStatus')
    #     if vehicle_status:
    #         response = self._get_vehicle_status(vehicle_status)
    #         self.vehicle.info = response
