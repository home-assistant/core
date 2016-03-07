"""
Support for exposing a templated binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.template/
"""
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice,
                                                    DOMAIN,
                                                    SENSOR_CLASSES)
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import EVENT_STATE_CHANGED
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers import template
from homeassistant.util import slugify

ENTITY_ID_FORMAT = DOMAIN + '.{}'
CONF_SENSORS = 'sensors'
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup template binary sensors."""
    sensors = []
    if config.get(CONF_SENSORS) is None:
        _LOGGER.error('Missing configuration data for binary_sensor platform')
        return False

    for device, device_config in config[CONF_SENSORS].items():

        if device != slugify(device):
            _LOGGER.error('Found invalid key for binary_sensor.template: %s. '
                          'Use %s instead', device, slugify(device))
            continue

        if not isinstance(device_config, dict):
            _LOGGER.error('Missing configuration data for binary_sensor %s',
                          device)
            continue

        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        sensor_class = device_config.get('sensor_class')
        value_template = device_config.get(CONF_VALUE_TEMPLATE)

        if sensor_class not in SENSOR_CLASSES:
            _LOGGER.error('Sensor class is not valid')
            continue

        if value_template is None:
            _LOGGER.error(
                'Missing %s for sensor %s', CONF_VALUE_TEMPLATE, device)
            continue

        sensors.append(
            BinarySensorTemplate(
                hass,
                device,
                friendly_name,
                sensor_class,
                value_template)
            )
    if not sensors:
        _LOGGER.error('No sensors added')
        return False
    add_devices(sensors)

    return True


class BinarySensorTemplate(BinarySensorDevice):
    """A virtual binary sensor that triggers from another sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, device, friendly_name, sensor_class,
                 value_template):
        """Initialize the Template binary sensor."""
        self._hass = hass
        self._device = device
        self._name = friendly_name
        self._sensor_class = sensor_class
        self._template = value_template
        self._state = None

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, device,
            hass=hass)

        _LOGGER.info('Started template sensor %s', device)
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    def _event_listener(self, event):
        if not hasattr(self, 'hass'):
            return
        self.update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def sensor_class(self):
        """Return the sensor class of the sensor."""
        return self._sensor_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        try:
            value = template.render(self._hass, self._template)
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning(ex)
                return
            _LOGGER.error(ex)
            value = 'false'
        self._state = value.lower() == 'true'
