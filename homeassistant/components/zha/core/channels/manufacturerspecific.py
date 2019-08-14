"""
Manufacturer specific channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

from . import AttributeListeningChannel
from .. import registries
from ..const import REPORT_CONFIG_ASAP, REPORT_CONFIG_MAX_INT, REPORT_CONFIG_MIN_INT


_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(registries.SMARTTHINGS_HUMIDITY_CLUSTER)
class SmartThingsHumidity(AttributeListeningChannel):
    """Smart Things Humidity channel."""

    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        }
    ]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    registries.SMARTTHINGS_ACCELERATION_CLUSTER
)
class SmartThingsAcceleration(AttributeListeningChannel):
    """Smart Things Acceleration channel."""

    REPORT_CONFIG = [
        {"attr": "acceleration", "config": REPORT_CONFIG_ASAP},
        {"attr": "x_axis", "config": REPORT_CONFIG_ASAP},
        {"attr": "y_axis", "config": REPORT_CONFIG_ASAP},
        {"attr": "z_axis", "config": REPORT_CONFIG_ASAP},
    ]
