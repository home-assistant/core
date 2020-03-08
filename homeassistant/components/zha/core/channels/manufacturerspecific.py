"""Manufacturer specific channels module for Zigbee Home Automation."""
import logging
from typing import Any

from homeassistant.core import callback

from .. import registries, typing as zha_typing
from ..const import (
    ATTR_ATTRIBUTE_ID,
    ATTR_ATTRIBUTE_NAME,
    ATTR_VALUE,
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
    SIGNAL_ATTR_UPDATED,
    UNKNOWN,
)
from .base import ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(registries.SMARTTHINGS_HUMIDITY_CLUSTER)
class SmartThingsHumidity(ZigbeeChannel):
    """Smart Things Humidity channel."""

    REPORT_CONFIG: zha_typing.AttributeReportConfigType = (
        zha_typing.AttributeReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        ),
    )


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFD00)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(0xFD00)
class OsramButton(ZigbeeChannel):
    """Osram button channel."""

    REPORT_CONFIG: zha_typing.AttributeReportConfigType = ()


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFCC0)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(0xFCC0)
class OppleRemote(ZigbeeChannel):
    """Opple button channel."""

    REPORT_CONFIG: zha_typing.AttributeReportConfigType = ()


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    registries.SMARTTHINGS_ACCELERATION_CLUSTER
)
class SmartThingsAcceleration(ZigbeeChannel):
    """Smart Things Acceleration channel."""

    REPORT_CONFIG: zha_typing.AttributeReportConfigType = (
        zha_typing.AttributeReportConfig(
            attr="acceleration", config=REPORT_CONFIG_ASAP
        ),
        zha_typing.AttributeReportConfig(attr="x_axis", config=REPORT_CONFIG_ASAP),
        zha_typing.AttributeReportConfig(attr="y_axis", config=REPORT_CONFIG_ASAP),
        zha_typing.AttributeReportConfig(attr="z_axis", config=REPORT_CONFIG_ASAP),
    )

    @callback
    def attribute_updated(self, attrid: int, value: Any) -> None:
        """Handle attribute updates on this cluster."""
        if attrid == self.value_attribute:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                attrid,
                self._cluster.attributes.get(attrid, [UNKNOWN])[0],
                value,
            )
            return

        self.zha_send_event(
            SIGNAL_ATTR_UPDATED,
            {
                ATTR_ATTRIBUTE_ID: attrid,
                ATTR_ATTRIBUTE_NAME: self._cluster.attributes.get(attrid, [UNKNOWN])[0],
                ATTR_VALUE: value,
            },
        )
