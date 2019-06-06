"""
Mapping registries for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

from .const import (
    HUMIDITY,
    TEMPERATURE, ILLUMINANCE, PRESSURE, METERING, ELECTRICAL_MEASUREMENT,
    OCCUPANCY, REPORT_CONFIG_IMMEDIATE, OPENING, ZONE, RADIO_DESCRIPTION,
    REPORT_CONFIG_ASAP, REPORT_CONFIG_DEFAULT, REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_MAX_INT, REPORT_CONFIG_OP, ACCELERATION, RadioType, RADIO,
    CONTROLLER
)

SMARTTHINGS_HUMIDITY_CLUSTER = 64581
SMARTTHINGS_ACCELERATION_CLUSTER = 64514

DEVICE_CLASS = {}
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
SENSOR_TYPES = {}
RADIO_TYPES = {}
BINARY_SENSOR_TYPES = {}
CLUSTER_REPORT_CONFIGS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
EVENT_RELAY_CLUSTERS = []
NO_SENSOR_CLUSTERS = []
BINDABLE_CLUSTERS = []
BINARY_SENSOR_CLUSTERS = set()
LIGHT_CLUSTERS = set()
SWITCH_CLUSTERS = set()
COMPONENT_CLUSTERS = {
    BINARY_SENSOR: BINARY_SENSOR_CLUSTERS,
    LIGHT: LIGHT_CLUSTERS,
    SWITCH: SWITCH_CLUSTERS
}


def establish_device_mappings():
    """Establish mappings between ZCL objects and HA ZHA objects.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    from zigpy import zcl
    from zigpy.profiles import zha, zll

    if zha.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zha.PROFILE_ID] = {}
    if zll.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zll.PROFILE_ID] = {}

    def get_ezsp_radio():
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication
        return {
            RADIO: bellows.ezsp.EZSP(),
            CONTROLLER: ControllerApplication
        }

    RADIO_TYPES[RadioType.ezsp.name] = {
        RADIO: get_ezsp_radio,
        RADIO_DESCRIPTION: 'EZSP'
    }

    def get_xbee_radio():
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication
        return {
            RADIO: zigpy_xbee.api.XBee(),
            CONTROLLER: ControllerApplication
        }

    RADIO_TYPES[RadioType.xbee.name] = {
        RADIO: get_xbee_radio,
        RADIO_DESCRIPTION: 'XBee'
    }

    def get_deconz_radio():
        import zigpy_deconz.api
        from zigpy_deconz.zigbee.application import ControllerApplication
        return {
            RADIO: zigpy_deconz.api.Deconz(),
            CONTROLLER: ControllerApplication
        }

    RADIO_TYPES[RadioType.deconz.name] = {
        RADIO: get_deconz_radio,
        RADIO_DESCRIPTION: 'Deconz'
    }

    EVENT_RELAY_CLUSTERS.append(zcl.clusters.general.LevelControl.cluster_id)
    EVENT_RELAY_CLUSTERS.append(zcl.clusters.general.OnOff.cluster_id)

    NO_SENSOR_CLUSTERS.append(zcl.clusters.general.Basic.cluster_id)
    NO_SENSOR_CLUSTERS.append(
        zcl.clusters.general.PowerConfiguration.cluster_id)
    NO_SENSOR_CLUSTERS.append(zcl.clusters.lightlink.LightLink.cluster_id)

    BINDABLE_CLUSTERS.append(zcl.clusters.general.LevelControl.cluster_id)
    BINDABLE_CLUSTERS.append(zcl.clusters.general.OnOff.cluster_id)
    BINDABLE_CLUSTERS.append(zcl.clusters.lighting.Color.cluster_id)

    DEVICE_CLASS[zha.PROFILE_ID].update({
        zha.DeviceType.ON_OFF_SWITCH: BINARY_SENSOR,
        zha.DeviceType.LEVEL_CONTROL_SWITCH: BINARY_SENSOR,
        zha.DeviceType.REMOTE_CONTROL: BINARY_SENSOR,
        zha.DeviceType.SMART_PLUG: SWITCH,
        zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: LIGHT,
        zha.DeviceType.ON_OFF_LIGHT: LIGHT,
        zha.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: LIGHT,
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: BINARY_SENSOR,
        zha.DeviceType.DIMMER_SWITCH: BINARY_SENSOR,
        zha.DeviceType.COLOR_DIMMER_SWITCH: BINARY_SENSOR,
    })

    DEVICE_CLASS[zll.PROFILE_ID].update({
        zll.DeviceType.ON_OFF_LIGHT: LIGHT,
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: SWITCH,
        zll.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: LIGHT,
        zll.DeviceType.COLOR_LIGHT: LIGHT,
        zll.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
        zll.DeviceType.COLOR_CONTROLLER: BINARY_SENSOR,
        zll.DeviceType.COLOR_SCENE_CONTROLLER: BINARY_SENSOR,
        zll.DeviceType.CONTROLLER: BINARY_SENSOR,
        zll.DeviceType.SCENE_CONTROLLER: BINARY_SENSOR,
        zll.DeviceType.ON_OFF_SENSOR: BINARY_SENSOR,
    })

    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: SWITCH,
        zcl.clusters.measurement.RelativeHumidity: SENSOR,
        # this works for now but if we hit conflicts we can break it out to
        # a different dict that is keyed by manufacturer
        SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR,
        zcl.clusters.measurement.TemperatureMeasurement: SENSOR,
        zcl.clusters.measurement.PressureMeasurement: SENSOR,
        zcl.clusters.measurement.IlluminanceMeasurement: SENSOR,
        zcl.clusters.smartenergy.Metering: SENSOR,
        zcl.clusters.homeautomation.ElectricalMeasurement: SENSOR,
        zcl.clusters.security.IasZone: BINARY_SENSOR,
        zcl.clusters.measurement.OccupancySensing: BINARY_SENSOR,
        zcl.clusters.hvac.Fan: FAN,
        SMARTTHINGS_ACCELERATION_CLUSTER: BINARY_SENSOR,
        zcl.clusters.general.MultistateInput.cluster_id: SENSOR,
        zcl.clusters.general.AnalogInput.cluster_id: SENSOR
    })

    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: BINARY_SENSOR,
    })

    SENSOR_TYPES.update({
        zcl.clusters.measurement.RelativeHumidity.cluster_id: HUMIDITY,
        SMARTTHINGS_HUMIDITY_CLUSTER: HUMIDITY,
        zcl.clusters.measurement.TemperatureMeasurement.cluster_id:
        TEMPERATURE,
        zcl.clusters.measurement.PressureMeasurement.cluster_id: PRESSURE,
        zcl.clusters.measurement.IlluminanceMeasurement.cluster_id:
        ILLUMINANCE,
        zcl.clusters.smartenergy.Metering.cluster_id: METERING,
        zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id:
        ELECTRICAL_MEASUREMENT,
    })

    BINARY_SENSOR_TYPES.update({
        zcl.clusters.measurement.OccupancySensing.cluster_id: OCCUPANCY,
        zcl.clusters.security.IasZone.cluster_id: ZONE,
        zcl.clusters.general.OnOff.cluster_id: OPENING,
        SMARTTHINGS_ACCELERATION_CLUSTER: ACCELERATION,
    })

    CLUSTER_REPORT_CONFIGS.update({
        zcl.clusters.general.Alarms.cluster_id: [],
        zcl.clusters.general.Basic.cluster_id: [],
        zcl.clusters.general.Commissioning.cluster_id: [],
        zcl.clusters.general.Identify.cluster_id: [],
        zcl.clusters.general.Groups.cluster_id: [],
        zcl.clusters.general.Scenes.cluster_id: [],
        zcl.clusters.general.Partition.cluster_id: [],
        zcl.clusters.general.Ota.cluster_id: [],
        zcl.clusters.general.PowerProfile.cluster_id: [],
        zcl.clusters.general.ApplianceControl.cluster_id: [],
        zcl.clusters.general.PollControl.cluster_id: [],
        zcl.clusters.general.GreenPowerProxy.cluster_id: [],
        zcl.clusters.general.OnOffConfiguration.cluster_id: [],
        zcl.clusters.lightlink.LightLink.cluster_id: [],
        zcl.clusters.general.OnOff.cluster_id: [{
            'attr': 'on_off',
            'config': REPORT_CONFIG_IMMEDIATE
        }],
        zcl.clusters.general.LevelControl.cluster_id: [{
            'attr': 'current_level',
            'config': REPORT_CONFIG_ASAP
        }],
        zcl.clusters.lighting.Color.cluster_id: [{
            'attr': 'current_x',
            'config': REPORT_CONFIG_DEFAULT
        }, {
            'attr': 'current_y',
            'config': REPORT_CONFIG_DEFAULT
        }, {
            'attr': 'color_temperature',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.measurement.RelativeHumidity.cluster_id: [{
            'attr': 'measured_value',
            'config': (
                REPORT_CONFIG_MIN_INT,
                REPORT_CONFIG_MAX_INT,
                50
            )
        }],
        zcl.clusters.measurement.TemperatureMeasurement.cluster_id: [{
            'attr': 'measured_value',
            'config': (
                REPORT_CONFIG_MIN_INT,
                REPORT_CONFIG_MAX_INT,
                50
            )
        }],
        SMARTTHINGS_ACCELERATION_CLUSTER: [{
            'attr': 'acceleration',
            'config': REPORT_CONFIG_ASAP
        }, {
            'attr': 'x_axis',
            'config': REPORT_CONFIG_ASAP
        }, {
            'attr': 'y_axis',
            'config': REPORT_CONFIG_ASAP
        }, {
            'attr': 'z_axis',
            'config': REPORT_CONFIG_ASAP
        }],
        SMARTTHINGS_HUMIDITY_CLUSTER: [{
            'attr': 'measured_value',
            'config': (
                REPORT_CONFIG_MIN_INT,
                REPORT_CONFIG_MAX_INT,
                50
            )
        }],
        zcl.clusters.measurement.PressureMeasurement.cluster_id: [{
            'attr': 'measured_value',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.measurement.IlluminanceMeasurement.cluster_id: [{
            'attr': 'measured_value',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.smartenergy.Metering.cluster_id: [{
            'attr': 'instantaneous_demand',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id: [{
            'attr': 'active_power',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.general.PowerConfiguration.cluster_id: [{
            'attr': 'battery_voltage',
            'config': REPORT_CONFIG_DEFAULT
        }, {
            'attr': 'battery_percentage_remaining',
            'config': REPORT_CONFIG_DEFAULT
        }],
        zcl.clusters.measurement.OccupancySensing.cluster_id: [{
            'attr': 'occupancy',
            'config': REPORT_CONFIG_IMMEDIATE
        }],
        zcl.clusters.hvac.Fan.cluster_id: [{
            'attr': 'fan_mode',
            'config': REPORT_CONFIG_OP
        }],
    })

    BINARY_SENSOR_CLUSTERS.add(zcl.clusters.general.OnOff.cluster_id)
    BINARY_SENSOR_CLUSTERS.add(zcl.clusters.general.LevelControl.cluster_id)
    BINARY_SENSOR_CLUSTERS.add(zcl.clusters.security.IasZone.cluster_id)
    BINARY_SENSOR_CLUSTERS.add(
        zcl.clusters.measurement.OccupancySensing.cluster_id)
    BINARY_SENSOR_CLUSTERS.add(SMARTTHINGS_ACCELERATION_CLUSTER)

    LIGHT_CLUSTERS.add(zcl.clusters.general.OnOff.cluster_id)
    LIGHT_CLUSTERS.add(zcl.clusters.general.LevelControl.cluster_id)
    LIGHT_CLUSTERS.add(zcl.clusters.lighting.Color.cluster_id)

    SWITCH_CLUSTERS.add(zcl.clusters.general.OnOff.cluster_id)
