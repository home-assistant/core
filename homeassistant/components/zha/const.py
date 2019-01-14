"""All constants related to the ZHA component."""
import enum

DOMAIN = 'zha'

BAUD_RATES = [
    2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000
]

DATA_ZHA = 'zha'
DATA_ZHA_CONFIG = 'config'
DATA_ZHA_BRIDGE_ID = 'zha_bridge_id'
DATA_ZHA_RADIO = 'zha_radio'
DATA_ZHA_DISPATCHERS = 'zha_dispatchers'
DATA_ZHA_CORE_COMPONENT = 'zha_core_component'
DATA_ZHA_CORE_EVENTS = 'zha_core_events'
ZHA_DISCOVERY_NEW = 'zha_discovery_new_{}'

COMPONENTS = [
    'binary_sensor',
    'fan',
    'light',
    'sensor',
    'switch',
]

CONF_BAUDRATE = 'baudrate'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
CONF_RADIO_TYPE = 'radio_type'
CONF_USB_PATH = 'usb_path'
DATA_DEVICE_CONFIG = 'zha_device_config'
ENABLE_QUIRKS = 'enable_quirks'

DEFAULT_RADIO_TYPE = 'ezsp'
DEFAULT_BAUDRATE = 57600
DEFAULT_DATABASE_NAME = 'zigbee.db'


class RadioType(enum.Enum):
    """Possible options for radio type."""

    ezsp = 'ezsp'
    xbee = 'xbee'

    @classmethod
    def list(cls):
        """Return list of enum's values."""
        return [e.value for e in RadioType]


DISCOVERY_KEY = 'zha_discovery_info'
DEVICE_CLASS = {}
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
COMPONENT_CLUSTERS = {}
EVENTABLE_CLUSTERS = []

REPORT_CONFIG_MAX_INT = 900
REPORT_CONFIG_MAX_INT_BATTERY_SAVE = 10800
REPORT_CONFIG_MIN_INT = 30
REPORT_CONFIG_MIN_INT_ASAP = 1
REPORT_CONFIG_MIN_INT_IMMEDIATE = 0
REPORT_CONFIG_MIN_INT_OP = 5
REPORT_CONFIG_MIN_INT_BATTERY_SAVE = 3600
REPORT_CONFIG_RPT_CHANGE = 1
REPORT_CONFIG_DEFAULT = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT,
                         REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_ASAP = (REPORT_CONFIG_MIN_INT_ASAP, REPORT_CONFIG_MAX_INT,
                      REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_BATTERY_SAVE = (REPORT_CONFIG_MIN_INT_BATTERY_SAVE,
                              REPORT_CONFIG_MAX_INT,
                              REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_IMMEDIATE = (REPORT_CONFIG_MIN_INT_IMMEDIATE,
                           REPORT_CONFIG_MAX_INT,
                           REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_OP = (REPORT_CONFIG_MIN_INT_OP, REPORT_CONFIG_MAX_INT,
                    REPORT_CONFIG_RPT_CHANGE)


def populate_data():
    """Populate data using constants from bellows.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    from zigpy import zcl, quirks
    from zigpy.profiles import PROFILES, zha, zll
    from homeassistant.components.sensor import zha as sensor_zha

    if zha.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zha.PROFILE_ID] = {}
    if zll.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zll.PROFILE_ID] = {}

    EVENTABLE_CLUSTERS.append(zcl.clusters.general.AnalogInput.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.LevelControl.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.MultistateInput.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.OnOff.cluster_id)

    DEVICE_CLASS[zha.PROFILE_ID].update({
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
    })
    DEVICE_CLASS[zll.PROFILE_ID].update({
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
    })

    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'switch',
        zcl.clusters.measurement.RelativeHumidity: 'sensor',
        zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
        zcl.clusters.measurement.PressureMeasurement: 'sensor',
        zcl.clusters.measurement.IlluminanceMeasurement: 'sensor',
        zcl.clusters.smartenergy.Metering: 'sensor',
        zcl.clusters.homeautomation.ElectricalMeasurement: 'sensor',
        zcl.clusters.general.PowerConfiguration: 'sensor',
        zcl.clusters.security.IasZone: 'binary_sensor',
        zcl.clusters.measurement.OccupancySensing: 'binary_sensor',
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

    # A map of hass components to all Zigbee clusters it could use
    for profile_id, classes in DEVICE_CLASS.items():
        profile = PROFILES[profile_id]
        for device_type, component in classes.items():
            if component not in COMPONENT_CLUSTERS:
                COMPONENT_CLUSTERS[component] = (set(), set())
            clusters = profile.CLUSTERS[device_type]
            COMPONENT_CLUSTERS[component][0].update(clusters[0])
            COMPONENT_CLUSTERS[component][1].update(clusters[1])
