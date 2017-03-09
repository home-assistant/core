"""Constants related to the zha component"""

from bellows.zigbee import zcl
from bellows.zigbee.profiles import zha, zll


DEVICE_CLASS = {
    zha.PROFILE_ID: {
        zha.DeviceType.ON_OFF_SWITCH: 'switch',
        zha.DeviceType.SMART_PLUG: 'switch',

        zha.DeviceType.ON_OFF_LIGHT: 'light',
        zha.DeviceType.DIMMABLE_LIGHT: 'light',
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: 'light',
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: 'light',
        zha.DeviceType.DIMMER_SWITCH: 'light',
        zha.DeviceType.COLOR_DIMMER_SWITCH: 'light',
    },
    zll.PROFILE_ID: {
        zll.DeviceType.ON_OFF_LIGHT: 'light',
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: 'switch',
        zll.DeviceType.DIMMABLE_LIGHT: 'light',
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: 'light',
        zll.DeviceType.COLOR_LIGHT: 'light',
        zll.DeviceType.EXTENDED_COLOR_LIGHT: 'light',
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
    },
}

SINGLE_CLUSTER_DEVICE_CLASS = {
    zcl.clusters.general.OnOff: 'switch',
    zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
    zcl.clusters.security.IasZone: 'binary_sensor',
}
