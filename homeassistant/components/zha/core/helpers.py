"""Helpers for Zigbee Home Automation."""
import collections
import logging

import zigpy.types

from homeassistant.core import callback

from .const import CLUSTER_TYPE_IN, CLUSTER_TYPE_OUT, DATA_ZHA, DATA_ZHA_GATEWAY
from .registries import BINDABLE_CLUSTERS

_LOGGER = logging.getLogger(__name__)

ClusterPair = collections.namedtuple("ClusterPair", "source_cluster target_cluster")


async def safe_read(
    cluster, attributes, allow_cache=True, only_cache=False, manufacturer=None
):
    """Swallow all exceptions from network read.

    If we throw during initialization, setup fails. Rather have an entity that
    exists, but is in a maybe wrong state, than no entity. This method should
    probably only be used during initialization.
    """
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=allow_cache,
            only_cache=only_cache,
            manufacturer=manufacturer,
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}


async def get_matched_clusters(source_zha_device, target_zha_device):
    """Get matched input/output cluster pairs for 2 devices."""
    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()
    clusters_to_bind = []

    for endpoint_id in source_clusters:
        for cluster_id in source_clusters[endpoint_id][CLUSTER_TYPE_OUT]:
            if cluster_id not in BINDABLE_CLUSTERS:
                continue
            for t_endpoint_id in target_clusters:
                if cluster_id in target_clusters[t_endpoint_id][CLUSTER_TYPE_IN]:
                    cluster_pair = ClusterPair(
                        source_cluster=source_clusters[endpoint_id][CLUSTER_TYPE_OUT][
                            cluster_id
                        ],
                        target_cluster=target_clusters[t_endpoint_id][CLUSTER_TYPE_IN][
                            cluster_id
                        ],
                    )
                    clusters_to_bind.append(cluster_pair)
    return clusters_to_bind


@callback
def async_is_bindable_target(source_zha_device, target_zha_device):
    """Determine if target is bindable to source."""
    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()

    for endpoint_id in source_clusters:
        for t_endpoint_id in target_clusters:
            matches = set(
                source_clusters[endpoint_id][CLUSTER_TYPE_OUT].keys()
            ).intersection(target_clusters[t_endpoint_id][CLUSTER_TYPE_IN].keys())
            if any(bindable in BINDABLE_CLUSTERS for bindable in matches):
                return True
    return False


async def async_get_zha_device(hass, device_id):
    """Get a ZHA device for the given device registry id."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    registry_device = device_registry.async_get(device_id)
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee_address = list(list(registry_device.identifiers)[0])[1]
    ieee = zigpy.types.EUI64.convert(ieee_address)
    return zha_gateway.devices[ieee]


class LogMixin:
    """Log helper."""

    def log(self, level, msg, *args):
        """Log with level."""
        raise NotImplementedError

    def debug(self, msg, *args):
        """Debug level log."""
        return self.log(logging.DEBUG, msg, *args)

    def info(self, msg, *args):
        """Info level log."""
        return self.log(logging.INFO, msg, *args)

    def warning(self, msg, *args):
        """Warning method log."""
        return self.log(logging.WARNING, msg, *args)

    def error(self, msg, *args):
        """Error level log."""
        return self.log(logging.ERROR, msg, *args)
