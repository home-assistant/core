"""
Manufacturer specific channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import AttributeListeningChannel, ZigbeeChannel
from .. import registries
from ..const import (
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
    SIGNAL_ATTR_UPDATED,
)

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


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFD00)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(0xFD00)
class OsramButton(ZigbeeChannel):
    """Osram button channel."""

    REPORT_CONFIG = []


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

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.value_attribute:
            async_dispatcher_send(
                self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", value
            )
        else:
            self.zha_send_event(
                self._cluster,
                SIGNAL_ATTR_UPDATED,
                {
                    "attribute_id": attrid,
                    "attribute_name": self._cluster.attributes.get(attrid, ["Unknown"])[
                        0
                    ],
                    "value": value,
                },
            )
