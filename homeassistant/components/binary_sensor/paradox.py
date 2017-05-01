"""
Support for Paradox Alarm zone states - represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.paradox/
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (STATE_OPEN, STATE_CLOSED)
from homeassistant.components.paradox import (PARADOX_CONTROLLER,
                                              ZONE_SCHEMA,
                                              CONF_ZONENAME,
                                              CONF_ZONETYPE)

DEPENDENCIES = ['paradox']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """
    Set up Paradox binary sensor platform.

    Based on configuration/yaml file contents, not auto discovery.
    """

    def update_zone_status_cb(zone_number):
        """Process the zone status change received from alarm panel."""
        # The zone on alarm panel might not be setup/defined in HA
        try:
            _affected_zone = ZONE_SCHEMA(_zones[zone_number])
            _LOGGER.debug('HA zone %s to be updated.',
                          _affected_zone[CONF_ZONENAME])

            _zone = 'binary_sensor.' + _affected_zone[CONF_ZONENAME]
            _zone.update_ha_state(True)
        except KeyError:
            _LOGGER.debug('Zone %d not defined in HA.', zone_number)

        return True

    # Overwrite the controllers default callback to call the hass function
    PARADOX_CONTROLLER.callback_zone_state_change = update_zone_status_cb

    # Get the zone information specified in the configuration/yaml file.
    _configured_zones = discovery_info['zones']
    for zone_num in _configured_zones:
        # For each zone specified, get the detail for that zone.
        _device_config_data = ZONE_SCHEMA(_configured_zones[zone_num])
        # Add the zone as a HA device.
        add_devices(
            [ParadoxBinarySensor(
                hass,
                zone_num,
                _device_config_data[CONF_ZONENAME],
                _device_config_data[CONF_ZONETYPE],
                PARADOX_CONTROLLER.alarm_state['zone'][zone_num]
                )])
    return True


class ParadoxBinarySensor(BinarySensorDevice):
    """Representation of an Paradox zone as a binary sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, zone_number, zone_name, zone_type, zone_info):
        """Initialize the Paradox zone as binary_sensor."""
        self._zone_mirror = zone_info  # As defined in Alarm State dictionary
        self._zone_type = zone_type
        self._zone_number = zone_number
        if zone_name in '':  # Only allow this if we may update the yaml file
            # When no label provided, get zone label from alarm panel
            # PARADOX_CONTROLLER.submit_zone_label_request(self._zone_number)
            # but it is asynchronous so set default name in the mean time
            self._name = self._zone_mirror['name']  # Alarm State default label
        else:
            self._name = zone_name  # Name in configuration/yaml file

        self._state = None
        # At startup Alarm State will not contain mirrored zone statuses yet
        # Request the zone status from the alarm panel
        PARADOX_CONTROLLER.submit_zone_status_request(self._zone_number)
        # No need to wait or call self.update() as status will be 
        # updated when it returns from controller.

        _LOGGER.debug('HA added zone: ' + zone_name)

    @property
    def name(self):
        """Return the name of the binary sensor device (Zone name/label)."""
        _LOGGER.debug('HA reports zone name as ' + self._name)
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is open."""
        _LOGGER.debug('HA is checking the status of %s', self._name)
        return self._zone_mirror['status']['open']

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_OPEN if self.is_on else STATE_CLOSED

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._zone_type

    @property
    def should_poll(self):
        """Zone status is pushed by alarm panel, so no polling needed."""
        return False

    def update(self):
        """Update the zone state."""
        # Controller updated Alarm State dictionary
        _LOGGER.debug('Updating zone status.')
        return self.state
