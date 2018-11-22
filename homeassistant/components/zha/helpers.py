"""
Helpers for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

_LOGGER = logging.getLogger(__name__)


def get_discovery_info(hass, discovery_info):
    """Get the full discovery info for a device.

    Some of the info that needs to be passed to platforms is not JSON
    serializable, so it cannot be put in the discovery_info dictionary. This
    component places that info we need to pass to the platform in hass.data,
    and this function is a helper for platforms to retrieve the complete
    discovery info.
    """
    if discovery_info is None:
        return

    import homeassistant.components.zha.const as zha_const
    discovery_key = discovery_info.get('discovery_key', None)
    all_discovery_info = hass.data.get(zha_const.DISCOVERY_KEY, {})
    return all_discovery_info.get(discovery_key, None)


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
