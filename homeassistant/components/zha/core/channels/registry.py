"""
Channel registry module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
from . import ZigbeeChannel
from .general import (
    OnOffChannel, LevelControlChannel, PowerConfigurationChannel, BasicChannel
)
from .homeautomation import ElectricalMeasurementChannel
from .hvac import FanChannel
from .lighting import ColorChannel
from .security import IASZoneChannel


ZIGBEE_CHANNEL_REGISTRY = {}


def populate_channel_registry():
    """Populate the channel registry."""
    from zigpy import zcl
    ZIGBEE_CHANNEL_REGISTRY.update({
        zcl.clusters.general.Alarms.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Commissioning.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Identify.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Groups.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Scenes.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Partition.cluster_id: ZigbeeChannel,
        zcl.clusters.general.Ota.cluster_id: ZigbeeChannel,
        zcl.clusters.general.PowerProfile.cluster_id: ZigbeeChannel,
        zcl.clusters.general.ApplianceControl.cluster_id: ZigbeeChannel,
        zcl.clusters.general.PollControl.cluster_id: ZigbeeChannel,
        zcl.clusters.general.GreenPowerProxy.cluster_id: ZigbeeChannel,
        zcl.clusters.general.OnOffConfiguration.cluster_id: ZigbeeChannel,
        zcl.clusters.general.OnOff.cluster_id: OnOffChannel,
        zcl.clusters.general.LevelControl.cluster_id: LevelControlChannel,
        zcl.clusters.lighting.Color.cluster_id: ColorChannel,
        zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id:
        ElectricalMeasurementChannel,
        zcl.clusters.general.PowerConfiguration.cluster_id:
        PowerConfigurationChannel,
        zcl.clusters.general.Basic.cluster_id: BasicChannel,
        zcl.clusters.security.IasZone.cluster_id: IASZoneChannel,
        zcl.clusters.hvac.Fan.cluster_id: FanChannel,
        zcl.clusters.lightlink.LightLink.cluster_id: ZigbeeChannel,
    })
