"""
Mapping registries for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import collections

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

from .const import (
    CONTROLLER,
    SENSOR_ACCELERATION,
    SENSOR_BATTERY,
    SENSOR_ELECTRICAL_MEASUREMENT,
    SENSOR_HUMIDITY,
    SENSOR_ILLUMINANCE,
    SENSOR_METERING,
    SENSOR_OCCUPANCY,
    SENSOR_OPENING,
    SENSOR_PRESSURE,
    SENSOR_TEMPERATURE,
    ZHA_GW_RADIO,
    ZHA_GW_RADIO_DESCRIPTION,
    ZONE,
    RadioType,
)
from .decorators import DictRegistry, SetRegistry

BINARY_SENSOR_CLUSTERS = SetRegistry()
BINARY_SENSOR_TYPES = {}
BINDABLE_CLUSTERS = SetRegistry()
CHANNEL_ONLY_CLUSTERS = SetRegistry()
CLUSTER_REPORT_CONFIGS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
DEVICE_CLASS = collections.defaultdict(dict)
DEVICE_TRACKER_CLUSTERS = SetRegistry()
EVENT_RELAY_CLUSTERS = SetRegistry()
LIGHT_CLUSTERS = SetRegistry()
OUTPUT_CHANNEL_ONLY_CLUSTERS = SetRegistry()
RADIO_TYPES = {}
REMOTE_DEVICE_TYPES = collections.defaultdict(list)
SENSOR_TYPES = {}
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
SWITCH_CLUSTERS = SetRegistry()
SMARTTHINGS_ACCELERATION_CLUSTER = 0xFC02
SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE = 0x8000
SMARTTHINGS_HUMIDITY_CLUSTER = 0xFC45

COMPONENT_CLUSTERS = {
    BINARY_SENSOR: BINARY_SENSOR_CLUSTERS,
    DEVICE_TRACKER: DEVICE_TRACKER_CLUSTERS,
    LIGHT: LIGHT_CLUSTERS,
    SWITCH: SWITCH_CLUSTERS,
}

ZIGBEE_CHANNEL_REGISTRY = DictRegistry()

# importing channels updates registries
from . import channels  # noqa pylint: disable=wrong-import-position,unused-import


def establish_device_mappings():
    """Establish mappings between ZCL objects and HA ZHA objects.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    from zigpy import zcl
    from zigpy.profiles import zha, zll

    def get_ezsp_radio():
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication

        return {ZHA_GW_RADIO: bellows.ezsp.EZSP(), CONTROLLER: ControllerApplication}

    RADIO_TYPES[RadioType.ezsp.name] = {
        ZHA_GW_RADIO: get_ezsp_radio,
        ZHA_GW_RADIO_DESCRIPTION: "EZSP",
    }

    def get_deconz_radio():
        import zigpy_deconz.api
        from zigpy_deconz.zigbee.application import ControllerApplication

        return {
            ZHA_GW_RADIO: zigpy_deconz.api.Deconz(),
            CONTROLLER: ControllerApplication,
        }

    RADIO_TYPES[RadioType.deconz.name] = {
        ZHA_GW_RADIO: get_deconz_radio,
        ZHA_GW_RADIO_DESCRIPTION: "Deconz",
    }

    def get_xbee_radio():
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication

        return {ZHA_GW_RADIO: zigpy_xbee.api.XBee(), CONTROLLER: ControllerApplication}

    RADIO_TYPES[RadioType.xbee.name] = {
        ZHA_GW_RADIO: get_xbee_radio,
        ZHA_GW_RADIO_DESCRIPTION: "XBee",
    }

    def get_zigate_radio():
        import zigpy_zigate.api
        from zigpy_zigate.zigbee.application import ControllerApplication

        return {
            ZHA_GW_RADIO: zigpy_zigate.api.ZiGate(),
            CONTROLLER: ControllerApplication,
        }

    RADIO_TYPES[RadioType.zigate.name] = {
        ZHA_GW_RADIO: get_zigate_radio,
        ZHA_GW_RADIO_DESCRIPTION: "ZiGate",
    }

    BINARY_SENSOR_CLUSTERS.add(SMARTTHINGS_ACCELERATION_CLUSTER)

    BINARY_SENSOR_TYPES.update(
        {
            SMARTTHINGS_ACCELERATION_CLUSTER: SENSOR_ACCELERATION,
            zcl.clusters.general.OnOff.cluster_id: SENSOR_OPENING,
            zcl.clusters.measurement.OccupancySensing.cluster_id: SENSOR_OCCUPANCY,
            zcl.clusters.security.IasZone.cluster_id: ZONE,
        }
    )

    DEVICE_CLASS[zha.PROFILE_ID].update(
        {
            SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE: DEVICE_TRACKER,
            zha.DeviceType.COLOR_DIMMABLE_LIGHT: LIGHT,
            zha.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
            zha.DeviceType.DIMMABLE_BALLAST: LIGHT,
            zha.DeviceType.DIMMABLE_LIGHT: LIGHT,
            zha.DeviceType.DIMMABLE_PLUG_IN_UNIT: LIGHT,
            zha.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
            zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: LIGHT,
            zha.DeviceType.ON_OFF_BALLAST: SWITCH,
            zha.DeviceType.ON_OFF_LIGHT: LIGHT,
            zha.DeviceType.ON_OFF_LIGHT_SWITCH: SWITCH,
            zha.DeviceType.ON_OFF_PLUG_IN_UNIT: SWITCH,
            zha.DeviceType.SMART_PLUG: SWITCH,
        }
    )

    DEVICE_CLASS[zll.PROFILE_ID].update(
        {
            zll.DeviceType.COLOR_LIGHT: LIGHT,
            zll.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
            zll.DeviceType.DIMMABLE_LIGHT: LIGHT,
            zll.DeviceType.DIMMABLE_PLUGIN_UNIT: LIGHT,
            zll.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
            zll.DeviceType.ON_OFF_LIGHT: LIGHT,
            zll.DeviceType.ON_OFF_PLUGIN_UNIT: SWITCH,
        }
    )

    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update(
        {
            # this works for now but if we hit conflicts we can break it out to
            # a different dict that is keyed by manufacturer
            SMARTTHINGS_ACCELERATION_CLUSTER: BINARY_SENSOR,
            SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR,
            zcl.clusters.closures.DoorLock: LOCK,
            zcl.clusters.general.AnalogInput.cluster_id: SENSOR,
            zcl.clusters.general.MultistateInput.cluster_id: SENSOR,
            zcl.clusters.general.OnOff: SWITCH,
            zcl.clusters.general.PowerConfiguration: SENSOR,
            zcl.clusters.homeautomation.ElectricalMeasurement: SENSOR,
            zcl.clusters.hvac.Fan: FAN,
            zcl.clusters.measurement.IlluminanceMeasurement: SENSOR,
            zcl.clusters.measurement.OccupancySensing: BINARY_SENSOR,
            zcl.clusters.measurement.PressureMeasurement: SENSOR,
            zcl.clusters.measurement.RelativeHumidity: SENSOR,
            zcl.clusters.measurement.TemperatureMeasurement: SENSOR,
            zcl.clusters.security.IasZone: BINARY_SENSOR,
            zcl.clusters.smartenergy.Metering: SENSOR,
        }
    )

    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.update(
        {zcl.clusters.general.OnOff: BINARY_SENSOR}
    )

    SENSOR_TYPES.update(
        {
            SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR_HUMIDITY,
            zcl.clusters.general.PowerConfiguration.cluster_id: SENSOR_BATTERY,
            zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id: SENSOR_ELECTRICAL_MEASUREMENT,
            zcl.clusters.measurement.IlluminanceMeasurement.cluster_id: SENSOR_ILLUMINANCE,
            zcl.clusters.measurement.PressureMeasurement.cluster_id: SENSOR_PRESSURE,
            zcl.clusters.measurement.RelativeHumidity.cluster_id: SENSOR_HUMIDITY,
            zcl.clusters.measurement.TemperatureMeasurement.cluster_id: SENSOR_TEMPERATURE,
            zcl.clusters.smartenergy.Metering.cluster_id: SENSOR_METERING,
        }
    )

    zhap = zha.PROFILE_ID
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.COLOR_DIMMER_SWITCH)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.COLOR_SCENE_CONTROLLER)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.DIMMER_SWITCH)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.NON_COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.NON_COLOR_SCENE_CONTROLLER)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.REMOTE_CONTROL)
    REMOTE_DEVICE_TYPES[zhap].append(zha.DeviceType.SCENE_SELECTOR)

    zllp = zll.PROFILE_ID
    REMOTE_DEVICE_TYPES[zllp].append(zll.DeviceType.COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zllp].append(zll.DeviceType.COLOR_SCENE_CONTROLLER)
    REMOTE_DEVICE_TYPES[zllp].append(zll.DeviceType.CONTROL_BRIDGE)
    REMOTE_DEVICE_TYPES[zllp].append(zll.DeviceType.CONTROLLER)
    REMOTE_DEVICE_TYPES[zllp].append(zll.DeviceType.SCENE_CONTROLLER)
