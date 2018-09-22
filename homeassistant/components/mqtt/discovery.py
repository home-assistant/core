"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import json
import logging
import re

from homeassistant.components import mqtt
from homeassistant.components.mqtt import CONF_STATE_TOPIC, ATTR_DISCOVERY_HASH
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r'(?P<prefix_topic>\w+)/(?P<component>\w+)/'
    r'(?:(?P<node_id>[a-zA-Z0-9_-]+)/)?(?P<object_id>[a-zA-Z0-9_-]+)/config')

SUPPORTED_COMPONENTS = [
    'binary_sensor', 'camera', 'cover', 'fan',
    'light', 'sensor', 'switch', 'lock', 'climate',
    'alarm_control_panel']

ALLOWED_PLATFORMS = {
    'binary_sensor': ['mqtt'],
    'camera': ['mqtt'],
    'cover': ['mqtt'],
    'fan': ['mqtt'],
    'light': ['mqtt', 'mqtt_json', 'mqtt_template'],
    'lock': ['mqtt'],
    'sensor': ['mqtt'],
    'switch': ['mqtt'],
    'climate': ['mqtt'],
    'alarm_control_panel': ['mqtt'],
}

CONFIG_ENTRY_PLATFORMS = {
    'binary_sensor': ['mqtt'],
    'camera': ['mqtt'],
    'cover': ['mqtt'],
    'light': ['mqtt'],
    'sensor': ['mqtt'],
    'switch': ['mqtt'],
    'climate': ['mqtt'],
    'alarm_control_panel': ['mqtt'],
}

ALREADY_DISCOVERED = 'mqtt_discovered_components'
CONFIG_ENTRY_IS_SETUP = 'mqtt_config_entry_is_setup'
MQTT_DISCOVERY_UPDATED = 'mqtt_discovery_updated_{}'
MQTT_DISCOVERY_NEW = 'mqtt_discovery_new_{}_{}'

TOPIC_PREFIX = '~'

ABBREVIATIONS = {
    'aft': 'after',
    'arm': 'arm',
    'attr': 'attributes',
    'aux': 'aux',
    'avty': 'availability',
    'avail': 'available',
    'away': 'away',
    'bri': 'brightness',
    'cla': 'class',
    'cls': 'close',
    'clsd': 'closed',
    'code': 'code',
    'clr': 'color',
    'cmd': 'command',
    'curr': 'current',
    'dev': 'device',
    'disarm': 'disarm',
    'fx': 'effect',
    'exp': 'expire',
    'fan': 'fan',
    'frc': 'force',
    'hi': 'high',
    'hold': 'hold',
    'home': 'home',
    'ic': 'icon',
    'id': 'id',
    'if': 'if',
    'init': 'initial',
    'inv': 'invert',
    'json': 'json',
    'list': 'list',
    'lock': 'lock',
    'lo': 'low',
    'max': 'max',
    'meas': 'measurement',
    'med': 'medium',
    'min': 'min',
    'mode': 'mode',
    'name': 'name',
    'not': 'not',
    'of': 'of',
    'off': 'off',
    'on': 'on',
    'open': 'open',
    'opnd': 'opened',
    'opt': 'optimistic',
    'osc': 'oscillation',
    'pl': 'payload',
    'pos': 'position',
    'pow': 'power',
    'qos': 'qos',
    'ret': 'retain',
    'rgb': 'rgb',
    'scl': 'scale',
    'send': 'send',
    'set': 'set',
    'spd': 'speed',
    'spds': 'speeds',
    'stat': 'state',
    'status': 'status',
    'stop': 'stop',
    'swing': 'swing',
    'temp': 'temp',
    'temperature': 'temperature',
    'tpl': 'template',
    'tilt': 'tilt',
    't': 'topic',
    'type': 'type',
    'uniq': 'unique',
    'unit': 'unit',
    'unlk': 'unlock',
    'upd': 'update',
    'val': 'value',
    'whit': 'white',
    'xy': 'xy',
}


async def async_start(hass: HomeAssistantType, discovery_topic, hass_config,
                      config_entry=None) -> bool:
    """Initialize of MQTT Discovery."""
    async def async_device_message_received(topic, payload, qos):
        """Process the received message."""
        match = TOPIC_MATCHER.match(topic)

        if not match:
            return

        _prefix_topic, component, node_id, object_id = match.groups()

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Component %s is not supported", component)
            return

        payload = dict(payload)

        for key in list(payload.keys()):
            abbreviated_key = key
            # Pattern to match one ore or word characters, excluding _, and:
            # - at beginning of string or prefixed by _
            # - at end of string or suffixed by _
            pattern = r'(?:(?<=^)|(?<=_))[^\W_]+(?=_|$)'

            def expand(matchobj):
                """Expand a possibly abbreviated word."""
                abbreviation = matchobj.group(0)
                if abbreviation in ABBREVIATIONS:
                    return ABBREVIATIONS[abbreviation]
                return abbreviation

            key = re.sub(pattern, expand, key)
            payload[key] = payload.pop(abbreviated_key)

        if TOPIC_PREFIX in payload:
            prefix = payload[TOPIC_PREFIX]
            for key, value in payload.items():
                if value.startswith(TOPIC_PREFIX) and key.endswith('_topic'):
                    payload[key] = "{}{}".format(prefix,
                                                 value[len(TOPIC_PREFIX):])

        # If present, the node_id will be included in the discovered object id
        discovery_id = '_'.join((node_id, object_id)) if node_id else object_id

        if ALREADY_DISCOVERED not in hass.data:
            hass.data[ALREADY_DISCOVERED] = {}

        discovery_hash = (component, discovery_id)

        if discovery_hash in hass.data[ALREADY_DISCOVERED]:
            _LOGGER.info(
                "Component has already been discovered: %s %s, sending update",
                component, discovery_id)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), payload)
        elif payload:
            # Add component
            try:
                payload = json.loads(payload)
            except ValueError:
                _LOGGER.warning("Unable to parse JSON %s: '%s'",
                                object_id, payload)
                return

            payload = dict(payload)
            platform = payload.get(CONF_PLATFORM, 'mqtt')
            if platform not in ALLOWED_PLATFORMS.get(component, []):
                _LOGGER.warning("Platform %s (component %s) is not allowed",
                                platform, component)
                return

            payload[CONF_PLATFORM] = platform
            if CONF_STATE_TOPIC not in payload:
                payload[CONF_STATE_TOPIC] = '{}/{}/{}{}/state'.format(
                    discovery_topic, component,
                    '%s/' % node_id if node_id else '', object_id)

            hass.data[ALREADY_DISCOVERED][discovery_hash] = None
            payload[ATTR_DISCOVERY_HASH] = discovery_hash

            _LOGGER.info("Found new component: %s %s", component, discovery_id)

            if platform not in CONFIG_ENTRY_PLATFORMS.get(component, []):
                await async_load_platform(
                    hass, component, platform, payload, hass_config)
                return

            config_entries_key = '{}.{}'.format(component, platform)
            if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)
                await hass.config_entries.async_forward_entry_setup(
                    config_entry, component)

            async_dispatcher_send(hass, MQTT_DISCOVERY_NEW.format(
                component, platform), payload)

    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    await mqtt.async_subscribe(
        hass, discovery_topic + '/#', async_device_message_received, 0)

    return True
