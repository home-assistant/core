"""All constants related to the ZHA component."""

import os
import logging

REMOTES_CONFIG_FILE = 'zha-remotes.json'
DEVICE_CLASS = {}
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
COMPONENT_CLUSTERS = {}
REMOTE_DEVICE_TYPES = {}

_LOGGER = logging.getLogger(__name__)


def populate_data(hass):
    """Populate data using constants from bellows.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    from zigpy import zcl, quirks
    from zigpy.profiles import PROFILES, zha, zll
    from homeassistant.components.sensor import zha as sensor_zha
    from homeassistant.util.json import load_json, save_json

    remotes_config_path = hass.config.path(REMOTES_CONFIG_FILE)

    _LOGGER.debug(
        "remotes config path: %s Is path: %s",
        remotes_config_path,
        os.path.isfile(remotes_config_path)
    )

    if not os.path.isfile(remotes_config_path):
        save_json(remotes_config_path,
                  {str(zha.PROFILE_ID): {}, str(zll.PROFILE_ID): {}}
                  )

    remote_devices = load_json(remotes_config_path)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID] = remote_devices.get(
        str(zha.PROFILE_ID)
        )
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID] = remote_devices.get(
        str(zll.PROFILE_ID)
        )

    _LOGGER.debug(
        "loaded from remotes config: %s", REMOTE_DEVICE_TYPES
    )

    DEVICE_CLASS[zha.PROFILE_ID] = {
        zha.DeviceType.ON_OFF_SWITCH: 'binary_sensor',
        zha.DeviceType.LEVEL_CONTROL_SWITCH: 'binary_sensor',
        zha.DeviceType.REMOTE_CONTROL: 'binary_sensor',
        zha.DeviceType.SMART_PLUG: 'switch',
        zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: 'light',
        zha.DeviceType.ON_OFF_LIGHT: 'light',
        zha.DeviceType.DIMMABLE_LIGHT: 'light',
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: 'light',
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: 'binary_sensor',
        zha.DeviceType.DIMMER_SWITCH: 'binary_sensor',
        zha.DeviceType.COLOR_DIMMER_SWITCH: 'binary_sensor',
    }
    DEVICE_CLASS[zll.PROFILE_ID] = {
        zll.DeviceType.ON_OFF_LIGHT: 'light',
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: 'switch',
        zll.DeviceType.DIMMABLE_LIGHT: 'light',
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: 'light',
        zll.DeviceType.COLOR_LIGHT: 'light',
        zll.DeviceType.EXTENDED_COLOR_LIGHT: 'light',
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
        zll.DeviceType.COLOR_CONTROLLER: 'binary_sensor',
        zll.DeviceType.COLOR_SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.CONTROLLER: 'binary_sensor',
        zll.DeviceType.SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.ON_OFF_SENSOR: 'binary_sensor',
    }
    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'switch',
        zcl.clusters.general.LevelControl: 'light',
        zcl.clusters.measurement.RelativeHumidity: 'sensor',
        zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
        zcl.clusters.measurement.PressureMeasurement: 'sensor',
        zcl.clusters.measurement.IlluminanceMeasurement: 'sensor',
        zcl.clusters.smartenergy.Metering: 'sensor',
        zcl.clusters.homeautomation.ElectricalMeasurement: 'sensor',
        zcl.clusters.security.IasZone: 'binary_sensor',
        zcl.clusters.hvac.Fan: 'fan',
    })
    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'binary_sensor',
    })

    # A map of device/cluster to component/sub-component
    CUSTOM_CLUSTER_MAPPINGS.update({
        (quirks.smartthings.SmartthingsTemperatureHumiditySensor, 64581):
            ('sensor', sensor_zha.RelativeHumiditySensor)
    })

    # This registers a device that Xiaomi didn't follow the spec on.
    # Translated: For device type: 0x5F01 in the ZHA zigbee profile
    # the input clusters are: [0x0000, 0x0006, 0xFFFF] and the output
    # clusters are: [0x0000, 0x0004, 0xFFFF]. The goal is to read this
    # from a configuration file in the future
    PROFILES[zha.PROFILE_ID].CLUSTERS[0x5F01] = ([0x0000, 0x0006, 0xFFFF],
                                                 [0x0000, 0x0004, 0xFFFF])

    # A map of hass components to all Zigbee clusters it could use
    for profile_id, classes in DEVICE_CLASS.items():
        profile = PROFILES[profile_id]
        for device_type, component in classes.items():
            if component not in COMPONENT_CLUSTERS:
                COMPONENT_CLUSTERS[component] = (set(), set())
            clusters = profile.CLUSTERS[device_type]
            COMPONENT_CLUSTERS[component][0].update(clusters[0])
            COMPONENT_CLUSTERS[component][1].update(clusters[1])
