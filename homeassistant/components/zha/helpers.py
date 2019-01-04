"""
Helpers for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
import logging

from .const import (
    DEFAULT_BAUDRATE, REPORT_CONFIG_MAX_INT, REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_RPT_CHANGE, RadioType)

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
    except DeliveryError as ex:
        _LOGGER.debug(
            "%s: Failed to bind '%s' cluster: %s",
            entity_id, cluster_name, str(ex)
        )


async def configure_reporting(entity_id, cluster, attr, skip_bind=False,
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
    cluster_name = cluster.ep_attribute
    kwargs = {}
    if manufacturer:
        kwargs['manufacturer'] = manufacturer
    try:
        res = await cluster.configure_reporting(attr, min_report,
                                                max_report, reportable_change,
                                                **kwargs)
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

    await configure_reporting(entity_id, cluster, attr, skip_bind=False,
                              min_report=REPORT_CONFIG_MIN_INT,
                              max_report=REPORT_CONFIG_MAX_INT,
                              reportable_change=REPORT_CONFIG_RPT_CHANGE,
                              manufacturer=None)


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
    try:
        await radio.connect(usb_path, DEFAULT_BAUDRATE)
        controller = ControllerApplication(radio, database_path)
        await asyncio.wait_for(controller.startup(auto_form=True), timeout=30)
        radio.close()
    except Exception:  # pylint: disable=broad-except
        return False
    return True
