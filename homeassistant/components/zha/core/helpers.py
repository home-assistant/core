"""
Helpers for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
import collections
import logging
from concurrent.futures import TimeoutError as Timeout
from homeassistant.core import callback
from .const import (
    DEFAULT_BAUDRATE, REPORT_CONFIG_MAX_INT, REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_RPT_CHANGE, RadioType, IN, OUT
)
from .registries import BINDABLE_CLUSTERS

_LOGGER = logging.getLogger(__name__)

ClusterPair = collections.namedtuple(
    'ClusterPair', 'source_cluster target_cluster')


async def safe_read(cluster, attributes, allow_cache=True, only_cache=False,
                    manufacturer=None):
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
            manufacturer=manufacturer
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}


async def bind_cluster(entity_id, cluster):
    """Bind a zigbee cluster.

    This also swallows DeliveryError exceptions that are thrown when devices
    are unreachable.
    """
    from zigpy.exceptions import DeliveryError

    cluster_name = cluster.ep_attribute
    try:
        res = await cluster.bind()
        _LOGGER.debug(
            "%s: bound  '%s' cluster: %s", entity_id, cluster_name, res[0]
        )
    except (DeliveryError, Timeout) as ex:
        _LOGGER.debug(
            "%s: Failed to bind '%s' cluster: %s",
            entity_id, cluster_name, str(ex)
        )


async def configure_reporting(entity_id, cluster, attr,
                              min_report=REPORT_CONFIG_MIN_INT,
                              max_report=REPORT_CONFIG_MAX_INT,
                              reportable_change=REPORT_CONFIG_RPT_CHANGE,
                              manufacturer=None):
    """Configure attribute reporting for a cluster.

    This also swallows DeliveryError exceptions that are thrown when devices
    are unreachable.
    """
    from zigpy.exceptions import DeliveryError

    attr_name = cluster.attributes.get(attr, [attr])[0]

    if isinstance(attr, str):
        attr_id = get_attr_id_by_name(cluster, attr_name)
    else:
        attr_id = attr

    cluster_name = cluster.ep_attribute
    kwargs = {}
    if manufacturer:
        kwargs['manufacturer'] = manufacturer
    try:
        res = await cluster.configure_reporting(attr_id, min_report,
                                                max_report, reportable_change,
                                                **kwargs)
        _LOGGER.debug(
            "%s: reporting '%s' attr on '%s' cluster: %d/%d/%d: Result: '%s'",
            entity_id, attr_name, cluster_name, min_report, max_report,
            reportable_change, res
        )
    except (DeliveryError, Timeout) as ex:
        _LOGGER.debug(
            "%s: failed to set reporting for '%s' attr on '%s' cluster: %s",
            entity_id, attr_name, cluster_name, str(ex)
        )


async def bind_configure_reporting(entity_id, cluster, attr, skip_bind=False,
                                   min_report=REPORT_CONFIG_MIN_INT,
                                   max_report=REPORT_CONFIG_MAX_INT,
                                   reportable_change=REPORT_CONFIG_RPT_CHANGE,
                                   manufacturer=None):
    """Bind and configure zigbee attribute reporting for a cluster.

    This also swallows DeliveryError exceptions that are thrown when devices
    are unreachable.
    """
    if not skip_bind:
        await bind_cluster(entity_id, cluster)

    await configure_reporting(entity_id, cluster, attr,
                              min_report=min_report,
                              max_report=max_report,
                              reportable_change=reportable_change,
                              manufacturer=manufacturer)


async def check_zigpy_connection(usb_path, radio_type, database_path):
    """Test zigpy radio connection."""
    if radio_type == RadioType.ezsp.name:
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication
        radio = bellows.ezsp.EZSP()
    elif radio_type == RadioType.xbee.name:
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication
        radio = zigpy_xbee.api.XBee()
    elif radio_type == RadioType.deconz.name:
        import zigpy_deconz.api
        from zigpy_deconz.zigbee.application import ControllerApplication
        radio = zigpy_deconz.api.Deconz()
    try:
        await radio.connect(usb_path, DEFAULT_BAUDRATE)
        controller = ControllerApplication(radio, database_path)
        await asyncio.wait_for(controller.startup(auto_form=True), timeout=30)
        await controller.shutdown()
    except Exception:  # pylint: disable=broad-except
        return False
    return True


def convert_ieee(ieee_str):
    """Convert given ieee string to EUI64."""
    from zigpy.types import EUI64, uint8_t
    if ieee_str is None:
        return None
    return EUI64([uint8_t(p, base=16) for p in ieee_str.split(':')])


def construct_unique_id(cluster):
    """Construct a unique id from a cluster."""
    return "0x{:04x}:{}:0x{:04x}".format(
        cluster.endpoint.device.nwk,
        cluster.endpoint.endpoint_id,
        cluster.cluster_id
    )


def get_attr_id_by_name(cluster, attr_name):
    """Get the attribute id for a cluster attribute by its name."""
    return next((attrid for attrid, (attrname, datatype) in
                 cluster.attributes.items() if attr_name == attrname), None)


async def get_matched_clusters(source_zha_device, target_zha_device):
    """Get matched input/output cluster pairs for 2 devices."""
    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()
    clusters_to_bind = []

    for endpoint_id in source_clusters:
        for cluster_id in source_clusters[endpoint_id][OUT]:
            if cluster_id not in BINDABLE_CLUSTERS:
                continue
            for t_endpoint_id in target_clusters:
                if cluster_id in target_clusters[t_endpoint_id][IN]:
                    cluster_pair = ClusterPair(
                        source_cluster=source_clusters[
                            endpoint_id][OUT][cluster_id],
                        target_cluster=target_clusters[
                            t_endpoint_id][IN][cluster_id]
                    )
                    clusters_to_bind.append(cluster_pair)
    return clusters_to_bind


@callback
def async_is_bindable_target(source_zha_device, target_zha_device):
    """Determine if target is bindable to source."""
    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()

    bindables = set(BINDABLE_CLUSTERS)
    for endpoint_id in source_clusters:
        for t_endpoint_id in target_clusters:
            matches = set(
                source_clusters[endpoint_id][OUT].keys()
                ).intersection(
                    target_clusters[t_endpoint_id][IN].keys()
                )
            if any(bindable in bindables for bindable in matches):
                return True
    return False
