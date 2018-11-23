"""
Helpers for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

_LOGGER = logging.getLogger(__name__)


async def safe_read(cluster, attributes, allow_cache=True, only_cache=False):
    """Swallow all exceptions from network read.

    If we throw during initialization, setup fails. Rather have an entity that
    exists, but is in a maybe wrong state, than no entity. This method should
    probably only be used during initialization.
    """
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=allow_cache,
            only_cache=only_cache
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}


async def configure_reporting(entity_id, cluster, attr, skip_bind=False,
                              min_report=300, max_report=900,
                              reportable_change=1):
    """Configure attribute reporting for a cluster.

    while swallowing the DeliverError exceptions in case of unreachable
    devices.
    """
    from zigpy.exceptions import DeliveryError

    attr_name = cluster.attributes.get(attr, [attr])[0]
    cluster_name = cluster.ep_attribute
    if not skip_bind:
        try:
            res = await cluster.bind()
            _LOGGER.debug(
                "%s: bound  '%s' cluster: %s", entity_id, cluster_name, res[0]
            )
        except DeliveryError as ex:
            _LOGGER.debug(
                "%s: Failed to bind '%s' cluster: %s",
                entity_id, cluster_name, str(ex)
            )

    try:
        res = await cluster.configure_reporting(attr, min_report,
                                                max_report, reportable_change)
        _LOGGER.debug(
            "%s: reporting '%s' attr on '%s' cluster: %d/%d/%d: Result: '%s'",
            entity_id, attr_name, cluster_name, min_report, max_report,
            reportable_change, res
        )
    except DeliveryError as ex:
        _LOGGER.debug(
            "%s: failed to set reporting for '%s' attr on '%s' cluster: %s",
            entity_id, attr_name, cluster_name, str(ex)
        )
