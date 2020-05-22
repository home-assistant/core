"""Helpers for Zigbee Home Automation."""
import collections
import logging
from typing import Any, Callable, Iterator, List, Optional

import zigpy.types

from homeassistant.core import State, callback

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


def find_state_attributes(states: List[State], key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        value = state.attributes.get(key)
        if value is not None:
            yield value


def mean_int(*args):
    """Return the mean of the supplied values."""
    return int(sum(args) / len(args))


def mean_tuple(*args):
    """Return the mean values along the columns of the supplied values."""
    return tuple(sum(x) / len(x) for x in zip(*args))


def reduce_attribute(
    states: List[State],
    key: str,
    default: Optional[Any] = None,
    reduce: Callable[..., Any] = mean_int,
) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)


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
