"""
Support for GPS tracking MQTT enabled devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mqtt_json/
"""
import asyncio
import json
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICES
from homeassistant.components.mqtt import CONF_QOS
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

_LOGGER = logging.getLogger(__name__)

LAT_KEY = 'lat'
LON_KEY = 'lon'
ACCURACY_KEY = 'acc'
BATTERY_KEY = 'batt'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend({
    vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Setup the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]

    dev_id_lookup = {}

    @callback
    def async_tracker_message_received(topic, payload, qos):
        """MQTT message received."""
        dev_id = dev_id_lookup[topic]

        try:
            data = json.loads(payload)
        except ValueError:
            _LOGGER.error('Unable to parse payload as JSON: %s', payload)
            return

        if not isinstance(data, dict):
            _LOGGER.debug('Skipping update for following data '
                          'because of missing or malformatted data: %s',
                          data)
            return

        if LON_KEY not in data or LAT_KEY not in data:
            _LOGGER.error('Skipping update for following data '
                          'because of missing gps coordinates: %s',
                          data)
            return

        kwargs = _parse_see_args(dev_id, data)
        hass.async_add_job(
            async_see(**kwargs))

    for dev_id, topic in devices.items():
        dev_id_lookup[topic] = dev_id
        yield from mqtt.async_subscribe(
            hass, topic, async_tracker_message_received, qos)

    return True


def _parse_see_args(dev_id, data):
    """Parse the payload location parameters, into the format see expects."""
    kwargs = {
        'gps': (data[LAT_KEY], data[LON_KEY]),
        'dev_id': dev_id
    }

    if 'acc' in data:
        kwargs['gps_accuracy'] = data[ACCURACY_KEY]
    if 'batt' in data:
        kwargs['battery'] = data[BATTERY_KEY]
    return kwargs
