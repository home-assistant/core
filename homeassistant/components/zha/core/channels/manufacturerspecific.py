"""Manufacturer specific channels module for Zigbee Home Automation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import zigpy.zcl

from homeassistant.core import callback

from .. import registries
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
from .base import AttrReportConfig, ClientChannel, ZigbeeChannel

if TYPE_CHECKING:
    from . import ChannelPool

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(registries.SMARTTHINGS_HUMIDITY_CLUSTER)
class SmartThingsHumidity(ZigbeeChannel):
    """Smart Things Humidity channel."""

    REPORT_CONFIG = (
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        },
    )


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFD00)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(0xFD00)
class OsramButton(ZigbeeChannel):
    """Osram button channel."""

    REPORT_CONFIG = ()


@registries.CHANNEL_ONLY_CLUSTERS.register(registries.PHILLIPS_REMOTE_CLUSTER)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(registries.PHILLIPS_REMOTE_CLUSTER)
class PhillipsRemote(ZigbeeChannel):
    """Phillips remote channel."""

    REPORT_CONFIG = ()


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFCC0)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(0xFCC0)
class OppleRemote(ZigbeeChannel):
    """Opple button channel."""

    REPORT_CONFIG = ()

    def __init__(self, cluster: zigpy.zcl.Cluster, ch_pool: ChannelPool) -> None:
        """Initialize Opple channel."""
        super().__init__(cluster, ch_pool)
        if self.cluster.endpoint.model == "lumi.motion.ac02":
            self.ZCL_INIT_ATTRS = {  # pylint: disable=invalid-name
                "detection_interval": True,
                "motion_sensitivity": True,
                "trigger_indicator": True,
            }

    async def async_initialize_channel_specific(self, from_cache: bool) -> None:
        """Initialize channel specific."""
        if self.cluster.endpoint.model == "lumi.motion.ac02":
            interval = self.cluster.get("detection_interval", self.cluster.get(0x0102))
            if interval is not None:
                self.debug("Loaded detection interval at startup: %s", interval)
                self.cluster.endpoint.ias_zone.reset_s = int(interval)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    registries.SMARTTHINGS_ACCELERATION_CLUSTER
)
class SmartThingsAcceleration(ZigbeeChannel):
    """Smart Things Acceleration channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="acceleration", config=REPORT_CONFIG_ASAP),
        AttrReportConfig(attr="x_axis", config=REPORT_CONFIG_ASAP),
        AttrReportConfig(attr="y_axis", config=REPORT_CONFIG_ASAP),
        AttrReportConfig(attr="z_axis", config=REPORT_CONFIG_ASAP),
    )

    @callback
    def attribute_updated(self, attrid, value):
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


@registries.CHANNEL_ONLY_CLUSTERS.register(0xFC31)
@registries.CLIENT_CHANNELS_REGISTRY.register(0xFC31)
class InovelliCluster(ClientChannel):
    """Inovelli Button Press Event channel."""

    REPORT_CONFIG = ()
