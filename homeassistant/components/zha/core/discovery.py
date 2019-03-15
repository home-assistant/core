"""
Device discovery functions for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging

from homeassistant import const as ha_const
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .channels import (
    AttributeListeningChannel, EventRelayChannel, ZDOChannel
)
from .channels.registry import ZIGBEE_CHANNEL_REGISTRY
from .const import (
    CONF_DEVICE_CONFIG, COMPONENTS, ZHA_DISCOVERY_NEW, DATA_ZHA,
    SENSOR_TYPE, UNKNOWN, GENERIC, POWER_CONFIGURATION_CHANNEL
)
from .registries import (
    BINARY_SENSOR_TYPES, NO_SENSOR_CLUSTERS, EVENT_RELAY_CLUSTERS,
    SENSOR_TYPES, DEVICE_CLASS, COMPONENT_CLUSTERS,
    SINGLE_INPUT_CLUSTER_DEVICE_CLASS, SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS
)
from ..device_entity import ZhaDeviceEntity

_LOGGER = logging.getLogger(__name__)


@callback
def async_process_endpoint(
        hass, config, endpoint_id, endpoint, discovery_infos, device,
        zha_device, is_new_join):
    """Process an endpoint on a zigpy device."""
    import zigpy.profiles

    if endpoint_id == 0:  # ZDO
        _async_create_cluster_channel(
            endpoint,
            zha_device,
            is_new_join,
            channel_class=ZDOChannel
        )
        return

    component = None
    profile_clusters = ([], [])
    device_key = "{}-{}".format(device.ieee, endpoint_id)
    node_config = {}
    if CONF_DEVICE_CONFIG in config:
        node_config = config[CONF_DEVICE_CONFIG].get(
            device_key, {}
        )

    if endpoint.profile_id in zigpy.profiles.PROFILES:
        profile = zigpy.profiles.PROFILES[endpoint.profile_id]
        if DEVICE_CLASS.get(endpoint.profile_id, {}).get(
                endpoint.device_type, None):
            profile_clusters = profile.CLUSTERS[endpoint.device_type]
            profile_info = DEVICE_CLASS[endpoint.profile_id]
            component = profile_info[endpoint.device_type]

    if ha_const.CONF_TYPE in node_config:
        component = node_config[ha_const.CONF_TYPE]
        profile_clusters = COMPONENT_CLUSTERS[component]

    if component and component in COMPONENTS:
        profile_match = _async_handle_profile_match(
            hass, endpoint, profile_clusters, zha_device,
            component, device_key, is_new_join)
        discovery_infos.append(profile_match)

    discovery_infos.extend(_async_handle_single_cluster_matches(
        hass,
        endpoint,
        zha_device,
        profile_clusters,
        device_key,
        is_new_join
    ))


@callback
def _async_create_cluster_channel(cluster, zha_device, is_new_join,
                                  channels=None, channel_class=None):
    """Create a cluster channel and attach it to a device."""
    if channel_class is None:
        channel_class = ZIGBEE_CHANNEL_REGISTRY.get(cluster.cluster_id,
                                                    AttributeListeningChannel)
    channel = channel_class(cluster, zha_device)
    zha_device.add_cluster_channel(channel)
    if channels is not None:
        channels.append(channel)


@callback
def async_dispatch_discovery_info(hass, is_new_join, discovery_info):
    """Dispatch or store discovery information."""
    if not discovery_info['channels']:
        _LOGGER.warning(
            "there are no channels in the discovery info: %s", discovery_info)
        return
    component = discovery_info['component']
    if is_new_join:
        async_dispatcher_send(
            hass,
            ZHA_DISCOVERY_NEW.format(component),
            discovery_info
        )
    else:
        hass.data[DATA_ZHA][component][discovery_info['unique_id']] = \
            discovery_info


@callback
def _async_handle_profile_match(hass, endpoint, profile_clusters, zha_device,
                                component, device_key, is_new_join):
    """Dispatch a profile match to the appropriate HA component."""
    in_clusters = [endpoint.in_clusters[c]
                   for c in profile_clusters[0]
                   if c in endpoint.in_clusters]
    out_clusters = [endpoint.out_clusters[c]
                    for c in profile_clusters[1]
                    if c in endpoint.out_clusters]

    channels = []

    for cluster in in_clusters:
        _async_create_cluster_channel(
            cluster, zha_device, is_new_join, channels=channels)

    for cluster in out_clusters:
        _async_create_cluster_channel(
            cluster, zha_device, is_new_join, channels=channels)

    discovery_info = {
        'unique_id': device_key,
        'zha_device': zha_device,
        'channels': channels,
        'component': component
    }

    if component == 'binary_sensor':
        discovery_info.update({SENSOR_TYPE: UNKNOWN})
        cluster_ids = []
        cluster_ids.extend(profile_clusters[0])
        cluster_ids.extend(profile_clusters[1])
        for cluster_id in cluster_ids:
            if cluster_id in BINARY_SENSOR_TYPES:
                discovery_info.update({
                    SENSOR_TYPE: BINARY_SENSOR_TYPES.get(
                        cluster_id, UNKNOWN)
                })
                break

    return discovery_info


@callback
def _async_handle_single_cluster_matches(hass, endpoint, zha_device,
                                         profile_clusters, device_key,
                                         is_new_join):
    """Dispatch single cluster matches to HA components."""
    cluster_matches = []
    cluster_match_results = []
    for cluster in endpoint.in_clusters.values():
        # don't let profiles prevent these channels from being created
        if cluster.cluster_id in NO_SENSOR_CLUSTERS:
            cluster_match_results.append(
                _async_handle_channel_only_cluster_match(
                    zha_device,
                    cluster,
                    is_new_join,
                ))

        if cluster.cluster_id not in profile_clusters[0]:
            cluster_match_results.append(_async_handle_single_cluster_match(
                hass,
                zha_device,
                cluster,
                device_key,
                SINGLE_INPUT_CLUSTER_DEVICE_CLASS,
                is_new_join,
            ))

    for cluster in endpoint.out_clusters.values():
        if cluster.cluster_id not in profile_clusters[1]:
            cluster_match_results.append(_async_handle_single_cluster_match(
                hass,
                zha_device,
                cluster,
                device_key,
                SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS,
                is_new_join,
            ))

        if cluster.cluster_id in EVENT_RELAY_CLUSTERS:
            _async_create_cluster_channel(
                cluster,
                zha_device,
                is_new_join,
                channel_class=EventRelayChannel
            )

    for cluster_match in cluster_match_results:
        if cluster_match is not None:
            cluster_matches.append(cluster_match)
    return cluster_matches


@callback
def _async_handle_channel_only_cluster_match(
        zha_device, cluster, is_new_join):
    """Handle a channel only cluster match."""
    _async_create_cluster_channel(cluster, zha_device, is_new_join)


@callback
def _async_handle_single_cluster_match(hass, zha_device, cluster, device_key,
                                       device_classes, is_new_join):
    """Dispatch a single cluster match to a HA component."""
    component = None  # sub_component = None
    for cluster_type, candidate_component in device_classes.items():
        if isinstance(cluster_type, int):
            if cluster.cluster_id == cluster_type:
                component = candidate_component
        elif isinstance(cluster, cluster_type):
            component = candidate_component
            break

    if component is None or component not in COMPONENTS:
        return
    channels = []
    _async_create_cluster_channel(cluster, zha_device, is_new_join,
                                  channels=channels)

    cluster_key = "{}-{}".format(device_key, cluster.cluster_id)
    discovery_info = {
        'unique_id': cluster_key,
        'zha_device': zha_device,
        'channels': channels,
        'entity_suffix': '_{}'.format(cluster.cluster_id),
        'component': component
    }

    if component == 'sensor':
        discovery_info.update({
            SENSOR_TYPE: SENSOR_TYPES.get(cluster.cluster_id, GENERIC)
        })
    if component == 'binary_sensor':
        discovery_info.update({
            SENSOR_TYPE: BINARY_SENSOR_TYPES.get(cluster.cluster_id, UNKNOWN)
        })

    return discovery_info


@callback
def async_create_device_entity(zha_device):
    """Create ZHADeviceEntity."""
    device_entity_channels = []
    if POWER_CONFIGURATION_CHANNEL in zha_device.cluster_channels:
        channel = zha_device.cluster_channels.get(POWER_CONFIGURATION_CHANNEL)
        device_entity_channels.append(channel)
    return ZhaDeviceEntity(zha_device, device_entity_channels)
