"""Support for MQTT discovery."""
import asyncio
import json
import logging
import re

from homeassistant.components import mqtt
from homeassistant.const import CONF_DEVICE, CONF_PLATFORM
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_DISCOVERY_HASH, CONF_STATE_TOPIC

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r'(?P<prefix_topic>\w+)/(?P<component>\w+)/'
    r'(?:(?P<node_id>[a-zA-Z0-9_-]+)/)?(?P<object_id>[a-zA-Z0-9_-]+)/config')

SUPPORTED_COMPONENTS = [
    'alarm_control_panel',
    'binary_sensor',
    'camera',
    'climate',
    'cover',
    'fan',
    'light',
    'lock',
    'sensor',
    'switch',
    'vacuum',
]

CONFIG_ENTRY_COMPONENTS = [
    'alarm_control_panel',
    'binary_sensor',
    'camera',
    'climate',
    'cover',
    'fan',
    'light',
    'lock',
    'sensor',
    'switch',
    'vacuum',
]

DEPRECATED_PLATFORM_TO_SCHEMA = {
    'light': {
        'mqtt_json': 'json',
        'mqtt_template': 'template',
    }
}

# These components require state_topic to be set.
# If not specified, infer state_topic from discovery topic.
IMPLICIT_STATE_TOPIC_COMPONENTS = [
    'alarm_control_panel',
    'binary_sensor',
    'sensor',
]


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
    'clr_temp_cmd_tpl': 'color_temp_command_template',
    'bat_lev_t': 'battery_level_topic',
    'bat_lev_tpl': 'battery_level_template',
    'chrg_t': 'charging_topic',
    'chrg_tpl': 'charging_template',
    'clr_temp_cmd_t': 'color_temp_command_topic',
    'clr_temp_stat_t': 'color_temp_state_topic',
    'clr_temp_val_tpl': 'color_temp_value_template',
    'cln_t': 'cleaning_topic',
    'cln_tpl': 'cleaning_template',
    'cmd_t': 'command_topic',
    'curr_temp_t': 'current_temperature_topic',
    'dev': 'device',
    'dev_cla': 'device_class',
    'dock_t': 'docked_topic',
    'dock_tpl': 'docked_template',
    'err_t': 'error_topic',
    'err_tpl': 'error_template',
    'fanspd_t': 'fan_speed_topic',
    'fanspd_tpl': 'fan_speed_template',
    'fanspd_lst': 'fan_speed_list',
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
    'json_attr_t': 'json_attributes_topic',
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
    'send_cmd_t': 'send_command_topic',
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
    'sup_feat': 'supported_features',
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
    'whit_val_scl': 'white_value_scale',
    'whit_val_stat_t': 'white_value_state_topic',
    'whit_val_tpl': 'white_value_template',
    'xy_cmd_t': 'xy_command_topic',
    'xy_stat_t': 'xy_state_topic',
    'xy_val_tpl': 'xy_value_template',
}

DEVICE_ABBREVIATIONS = {
    'cns': 'connections',
    'ids': 'identifiers',
    'name': 'name',
    'mf': 'manufacturer',
    'mdl': 'model',
    'sw': 'sw_version',
}


def clear_discovery_hash(hass, discovery_hash):
    """Clear entry in ALREADY_DISCOVERED list."""
    del hass.data[ALREADY_DISCOVERED][discovery_hash]


async def async_start(hass: HomeAssistantType, discovery_topic, hass_config,
                      config_entry=None) -> bool:
    """Initialize of MQTT Discovery."""
    async def async_device_message_received(msg):
        """Process the received message."""
        payload = msg.payload
        topic = msg.topic
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

        if CONF_DEVICE in payload:
            device = payload[CONF_DEVICE]
            for key in list(device.keys()):
                abbreviated_key = key
                key = DEVICE_ABBREVIATIONS.get(key, key)
                device[key] = device.pop(abbreviated_key)

        if TOPIC_BASE in payload:
            base = payload.pop(TOPIC_BASE)
            for key, value in payload.items():
                if isinstance(value, str) and value:
                    if value[0] == TOPIC_BASE and key.endswith('_topic'):
                        payload[key] = "{}{}".format(base, value[1:])
                    if value[-1] == TOPIC_BASE and key.endswith('_topic'):
                        payload[key] = "{}{}".format(value[:-1], base)

        # If present, the node_id will be included in the discovered object id
        discovery_id = ' '.join((node_id, object_id)) if node_id else object_id
        discovery_hash = (component, discovery_id)

        if payload:
            if CONF_PLATFORM in payload and 'schema' not in payload:
                platform = payload[CONF_PLATFORM]
                if (component in DEPRECATED_PLATFORM_TO_SCHEMA and
                        platform in DEPRECATED_PLATFORM_TO_SCHEMA[component]):
                    schema = DEPRECATED_PLATFORM_TO_SCHEMA[component][platform]
                    payload['schema'] = schema
                    _LOGGER.warning('"platform": "%s" is deprecated, '
                                    'replace with "schema":"%s"',
                                    platform, schema)
            payload[CONF_PLATFORM] = 'mqtt'

            if (CONF_STATE_TOPIC not in payload and
                    component in IMPLICIT_STATE_TOPIC_COMPONENTS):
                # state_topic not specified, infer from discovery topic
                payload[CONF_STATE_TOPIC] = '{}/{}/{}{}/state'.format(
                    discovery_topic, component,
                    '%s/' % node_id if node_id else '', object_id)
                _LOGGER.warning('implicit %s is deprecated, add "%s":"%s" to '
                                '%s discovery message',
                                CONF_STATE_TOPIC, CONF_STATE_TOPIC,
                                payload[CONF_STATE_TOPIC], topic)

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
