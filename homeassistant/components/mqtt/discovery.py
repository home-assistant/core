"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import asyncio
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

CONFIG_ENTRY_COMPONENTS = [
    'binary_sensor',
    'camera',
    'cover',
    'light',
    'lock',
    'sensor',
    'switch',
    'climate',
    'alarm_control_panel',
    'fan',
]

DEPRECATED_PLATFORM_TO_SCHEMA = {
    'mqtt': 'basic',
    'mqtt_json': 'json',
    'mqtt_template': 'template',
}


ALREADY_DISCOVERED = 'mqtt_discovered_components'
DATA_CONFIG_ENTRY_LOCK = 'mqtt_config_entry_lock'
CONFIG_ENTRY_IS_SETUP = 'mqtt_config_entry_is_setup'
MQTT_DISCOVERY_UPDATED = 'mqtt_discovery_updated_{}'
MQTT_DISCOVERY_NEW = 'mqtt_discovery_new_{}_{}'

TOPIC_BASE = '~'

ABBREVIATIONS = {
    'aux_cmd_t': 'aux_command_topic',
    'aux_stat_tpl': 'aux_state_template',
    'aux_stat_t': 'aux_state_topic',
    'avty_t': 'availability_topic',
    'away_mode_cmd_t': 'away_mode_command_topic',
    'away_mode_stat_tpl': 'away_mode_state_template',
    'away_mode_stat_t': 'away_mode_state_topic',
    'bri_cmd_t': 'brightness_command_topic',
    'bri_scl': 'brightness_scale',
    'bri_stat_t': 'brightness_state_topic',
    'bri_val_tpl': 'brightness_value_template',
    'clr_temp_cmd_t': 'color_temp_command_topic',
    'clr_temp_stat_t': 'color_temp_state_topic',
    'clr_temp_val_tpl': 'color_temp_value_template',
    'cmd_t': 'command_topic',
    'curr_temp_t': 'current_temperature_topic',
    'dev_cla': 'device_class',
    'fx_cmd_t': 'effect_command_topic',
    'fx_list': 'effect_list',
    'fx_stat_t': 'effect_state_topic',
    'fx_val_tpl': 'effect_value_template',
    'exp_aft': 'expire_after',
    'fan_mode_cmd_t': 'fan_mode_command_topic',
    'fan_mode_stat_tpl': 'fan_mode_state_template',
    'fan_mode_stat_t': 'fan_mode_state_topic',
    'frc_upd': 'force_update',
    'hold_cmd_t': 'hold_command_topic',
    'hold_stat_tpl': 'hold_state_template',
    'hold_stat_t': 'hold_state_topic',
    'ic': 'icon',
    'init': 'initial',
    'json_attr': 'json_attributes',
    'max_temp': 'max_temp',
    'min_temp': 'min_temp',
    'mode_cmd_t': 'mode_command_topic',
    'mode_stat_tpl': 'mode_state_template',
    'mode_stat_t': 'mode_state_topic',
    'name': 'name',
    'on_cmd_type': 'on_command_type',
    'opt': 'optimistic',
    'osc_cmd_t': 'oscillation_command_topic',
    'osc_stat_t': 'oscillation_state_topic',
    'osc_val_tpl': 'oscillation_value_template',
    'pl_arm_away': 'payload_arm_away',
    'pl_arm_home': 'payload_arm_home',
    'pl_avail': 'payload_available',
    'pl_cls': 'payload_close',
    'pl_disarm': 'payload_disarm',
    'pl_hi_spd': 'payload_high_speed',
    'pl_lock': 'payload_lock',
    'pl_lo_spd': 'payload_low_speed',
    'pl_med_spd': 'payload_medium_speed',
    'pl_not_avail': 'payload_not_available',
    'pl_off': 'payload_off',
    'pl_on': 'payload_on',
    'pl_open': 'payload_open',
    'pl_osc_off': 'payload_oscillation_off',
    'pl_osc_on': 'payload_oscillation_on',
    'pl_stop': 'payload_stop',
    'pl_unlk': 'payload_unlock',
    'pow_cmd_t': 'power_command_topic',
    'ret': 'retain',
    'rgb_cmd_tpl': 'rgb_command_template',
    'rgb_cmd_t': 'rgb_command_topic',
    'rgb_stat_t': 'rgb_state_topic',
    'rgb_val_tpl': 'rgb_value_template',
    'send_if_off': 'send_if_off',
    'set_pos_tpl': 'set_position_template',
    'set_pos_t': 'set_position_topic',
    'spd_cmd_t': 'speed_command_topic',
    'spd_stat_t': 'speed_state_topic',
    'spd_val_tpl': 'speed_value_template',
    'spds': 'speeds',
    'stat_clsd': 'state_closed',
    'stat_off': 'state_off',
    'stat_on': 'state_on',
    'stat_open': 'state_open',
    'stat_t': 'state_topic',
    'stat_val_tpl': 'state_value_template',
    'swing_mode_cmd_t': 'swing_mode_command_topic',
    'swing_mode_stat_tpl': 'swing_mode_state_template',
    'swing_mode_stat_t': 'swing_mode_state_topic',
    'temp_cmd_t': 'temperature_command_topic',
    'temp_stat_tpl': 'temperature_state_template',
    'temp_stat_t': 'temperature_state_topic',
    'tilt_clsd_val': 'tilt_closed_value',
    'tilt_cmd_t': 'tilt_command_topic',
    'tilt_inv_stat': 'tilt_invert_state',
    'tilt_max': 'tilt_max',
    'tilt_min': 'tilt_min',
    'tilt_opnd_val': 'tilt_opened_value',
    'tilt_status_opt': 'tilt_status_optimistic',
    'tilt_status_t': 'tilt_status_topic',
    't': 'topic',
    'uniq_id': 'unique_id',
    'unit_of_meas': 'unit_of_measurement',
    'val_tpl': 'value_template',
    'whit_val_cmd_t': 'white_value_command_topic',
    'whit_val_stat_t': 'white_value_state_topic',
    'whit_val_tpl': 'white_value_template',
    'xy_cmd_t': 'xy_command_topic',
    'xy_stat_t': 'xy_state_topic',
    'xy_val_tpl': 'xy_value_template',
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

        if payload:
            try:
                payload = json.loads(payload)
            except ValueError:
                _LOGGER.warning("Unable to parse JSON %s: '%s'",
                                object_id, payload)
                return

        payload = dict(payload)

        for key in list(payload.keys()):
            abbreviated_key = key
            key = ABBREVIATIONS.get(key, key)
            payload[key] = payload.pop(abbreviated_key)

        if TOPIC_BASE in payload:
            base = payload[TOPIC_BASE]
            for key, value in payload.items():
                if isinstance(value, str):
                    if value[0] == TOPIC_BASE and key.endswith('_topic'):
                        payload[key] = "{}{}".format(base, value[1:])
                    if value[-1] == TOPIC_BASE and key.endswith('_topic'):
                        payload[key] = "{}{}".format(value[:-1], base)

        # If present, the node_id will be included in the discovered object id
        discovery_id = ' '.join((node_id, object_id)) if node_id else object_id
        discovery_hash = (component, discovery_id)

        if payload:
            if CONF_PLATFORM in payload:
                platform = payload[CONF_PLATFORM]
                if platform in DEPRECATED_PLATFORM_TO_SCHEMA:
                    schema = DEPRECATED_PLATFORM_TO_SCHEMA[platform]
                    payload['schema'] = schema
                    _LOGGER.warning('"platform": "%s" is deprecated, '
                                    'replace with "schema":"%s"',
                                    platform, schema)
            payload[CONF_PLATFORM] = 'mqtt'

            if CONF_STATE_TOPIC not in payload:
                payload[CONF_STATE_TOPIC] = '{}/{}/{}{}/state'.format(
                    discovery_topic, component,
                    '%s/' % node_id if node_id else '', object_id)

            payload[ATTR_DISCOVERY_HASH] = discovery_hash

        if ALREADY_DISCOVERED not in hass.data:
            hass.data[ALREADY_DISCOVERED] = {}
        if discovery_hash in hass.data[ALREADY_DISCOVERED]:
            # Dispatch update
            _LOGGER.info(
                "Component has already been discovered: %s %s, sending update",
                component, discovery_id)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), payload)
        elif payload:
            # Add component
            _LOGGER.info("Found new component: %s %s", component, discovery_id)
            hass.data[ALREADY_DISCOVERED][discovery_hash] = None

            if component not in CONFIG_ENTRY_COMPONENTS:
                await async_load_platform(
                    hass, component, 'mqtt', payload, hass_config)
                return

            config_entries_key = '{}.{}'.format(component, 'mqtt')
            async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
                if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                    await hass.config_entries.async_forward_entry_setup(
                        config_entry, component)
                    hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

            async_dispatcher_send(hass, MQTT_DISCOVERY_NEW.format(
                component, 'mqtt'), payload)

    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    await mqtt.async_subscribe(
        hass, discovery_topic + '/#', async_device_message_received, 0)

    return True
