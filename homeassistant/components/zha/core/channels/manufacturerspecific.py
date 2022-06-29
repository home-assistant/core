"""Manufacturer specific channels module for Zigbee Home Automation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from zigpy.exceptions import ZigbeeException
import zigpy.zcl

from homeassistant.core import callback

from .. import registries
from ..const import (
    ATTR_ATTRIBUTE_ID,
    ATTR_ATTRIBUTE_NAME,
    ATTR_VALUE,
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
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
        elif self.cluster.endpoint.model == "lumi.motion.ac01":
            self.ZCL_INIT_ATTRS = {  # pylint: disable=invalid-name
                "presence": True,
                "monitoring_mode": True,
                "motion_sensitivity": True,
                "approach_distance": True,
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


@registries.CHANNEL_ONLY_CLUSTERS.register(registries.IKEA_AIR_PURIFIER_CLUSTER)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(registries.IKEA_AIR_PURIFIER_CLUSTER)
class IkeaAirPurifierChannel(ZigbeeChannel):
    """IKEA Air Purifier channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="filter_run_time", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="replace_filter", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="filter_life_time", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="disable_led", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="air_quality_25pm", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="child_lock", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="fan_mode", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="fan_speed", config=REPORT_CONFIG_IMMEDIATE),
        AttrReportConfig(attr="device_run_time", config=REPORT_CONFIG_DEFAULT),
    )

    @property
    def fan_mode(self) -> int | None:
        """Return current fan mode."""
        return self.cluster.get("fan_mode")

    @property
    def fan_mode_sequence(self) -> int | None:
        """Return possible fan mode speeds."""
        return self.cluster.get("fan_mode_sequence")

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""

        try:
            await self.cluster.write_attributes({"fan_mode": value})
        except ZigbeeException as ex:
            self.error("Could not set speed: %s", ex)
            return

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self.get_attribute_value("fan_mode", from_cache=False)

    @callback
    def attribute_updated(self, attrid: int, value: Any) -> None:
        """Handle attribute update from fan cluster."""
        attr_name = self._get_attribute_name(attrid)
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attr_name == "fan_mode":
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )
