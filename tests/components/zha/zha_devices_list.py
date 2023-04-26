"""Example Zigbee Devices."""

from zigpy.const import (
    SIG_ENDPOINTS,
    SIG_EP_INPUT,
    SIG_EP_OUTPUT,
    SIG_EP_PROFILE,
    SIG_EP_TYPE,
    SIG_MANUFACTURER,
    SIG_MODEL,
    SIG_NODE_DESC,
)
from zigpy.profiles import zha
from zigpy.zcl.clusters.closures import DoorLock
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    MultistateInput,
    Ota,
    Scenes,
)

DEV_SIG_CLUSTER_HANDLERS = "cluster_handlers"
DEV_SIG_DEV_NO = "device_no"
DEV_SIG_ENT_MAP = "entity_map"
DEV_SIG_ENT_MAP_CLASS = "entity_class"
DEV_SIG_ENT_MAP_ID = "entity_id"
DEV_SIG_EP_ID = "endpoint_id"
DEV_SIG_EVT_CLUSTER_HANDLERS = "event_cluster_handlers"
DEV_SIG_ZHA_QUIRK = "zha_quirk"
DEV_SIG_ATTRIBUTES = "attributes"


PROFILE_ID = SIG_EP_PROFILE
DEVICE_TYPE = SIG_EP_TYPE
INPUT_CLUSTERS = SIG_EP_INPUT
OUTPUT_CLUSTERS = SIG_EP_OUTPUT

DEVICES = [
    {
        DEV_SIG_DEV_NO: 0,
        SIG_MANUFACTURER: "ADUROLIGHT",
        SIG_MODEL: "Adurolight_NCC",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2080,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4096, 64716],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 4096, 64716],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.adurolight_adurolight_ncc_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.adurolight_adurolight_ncc_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.adurolight_adurolight_ncc_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 1,
        SIG_MANUFACTURER: "Bosch",
        SIG_MODEL: "ISW-ZPR1-WP13",
        SIG_NODE_DESC: b"\x02@\x08\x00\x00l\x00\x00\x00\x00\x00\x00\x00",
        SIG_ENDPOINTS: {
            5: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["5:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-5-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.bosch_isw_zpr1_wp13_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-5-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.bosch_isw_zpr1_wp13_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 2,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3130",
        SIG_NODE_DESC: b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 2821],
                SIG_EP_OUTPUT: [3, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3130_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3130_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3130_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3130_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 3,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3210-L",
        SIG_NODE_DESC: b"\x01@\x8eN\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 1794, 2820, 2821, 64515],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.centralite_3210_l_switch",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3210_l_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 4,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3310-S",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 770,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 2821, 64581],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3310_s_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-64581"): {
                DEV_SIG_CLUSTER_HANDLERS: ["humidity"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_humidity",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 5,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3315-S",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 12,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821, 64527],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 49887,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3315_s_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3315_s_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 6,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3320-L",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 12,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821, 64527],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 49887,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3320_l_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3320_l_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 7,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3326-L",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 263,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821, 64582],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 49887,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3326_l_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_3326_l_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 8,
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "Motion Sensor-A",
        SIG_NODE_DESC: b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 263,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 1030, 2821],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_motion_sensor_a_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.centralite_motion_sensor_a_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-2-1030"): {
                DEV_SIG_CLUSTER_HANDLERS: ["occupancy"],
                DEV_SIG_ENT_MAP_CLASS: "Occupancy",
                DEV_SIG_ENT_MAP_ID: (
                    "binary_sensor.centralite_motion_sensor_a_occupancy"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 9,
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "PSMP5_00.00.02.02TC",
        SIG_NODE_DESC: b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 1794],
                SIG_EP_OUTPUT: [0],
                SIG_EP_PROFILE: 260,
            },
            4: {
                SIG_EP_TYPE: 9,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["4:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: (
                    "switch.climaxtechnology_psmp5_00_00_02_02tc_switch"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.climaxtechnology_psmp5_00_00_02_02tc_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.climaxtechnology_psmp5_00_00_02_02tc_instantaneous_demand"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.climaxtechnology_psmp5_00_00_02_02tc_summation_delivered"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_psmp5_00_00_02_02tc_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_psmp5_00_00_02_02tc_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 10,
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "SD8SC_00.00.03.12TC",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 1280, 1282],
                SIG_EP_OUTPUT: [0],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: (
                    "binary_sensor.climaxtechnology_sd8sc_00_00_03_12tc_iaszone"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.climaxtechnology_sd8sc_00_00_03_12tc_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_sd8sc_00_00_03_12tc_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_sd8sc_00_00_03_12tc_lqi",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-WarningMode"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultToneSelectEntity",
                DEV_SIG_ENT_MAP_ID: (
                    "select.climaxtechnology_sd8sc_00_00_03_12tc_default_siren_tone"
                ),
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-SirenLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultSirenLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: (
                    "select.climaxtechnology_sd8sc_00_00_03_12tc_default_siren_level"
                ),
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-StrobeLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: (
                    "select.climaxtechnology_sd8sc_00_00_03_12tc_default_strobe_level"
                ),
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-Strobe"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeSelectEntity",
                DEV_SIG_ENT_MAP_ID: (
                    "select.climaxtechnology_sd8sc_00_00_03_12tc_default_strobe"
                ),
            },
            ("siren", "00:11:22:33:44:55:66:77-1-1282"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHASiren",
                DEV_SIG_ENT_MAP_ID: "siren.climaxtechnology_sd8sc_00_00_03_12tc_siren",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 11,
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "WS15_00.00.03.03TC",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 1280],
                SIG_EP_OUTPUT: [0],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: (
                    "binary_sensor.climaxtechnology_ws15_00_00_03_03tc_iaszone"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.climaxtechnology_ws15_00_00_03_03tc_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_ws15_00_00_03_03tc_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_ws15_00_00_03_03tc_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 12,
        SIG_MANUFACTURER: "Feibit Inc co.",
        SIG_MODEL: "FB56-ZCW08KU1.1",
        SIG_NODE_DESC: b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            11: {
                SIG_EP_TYPE: 528,
                DEV_SIG_EP_ID: 11,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49246,
            },
            13: {
                SIG_EP_TYPE: 57694,
                DEV_SIG_EP_ID: 13,
                SIG_EP_INPUT: [4096],
                SIG_EP_OUTPUT: [4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-11"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "light_color", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.feibit_inc_co_fb56_zcw08ku1_1_light",
            },
            ("button", "00:11:22:33:44:55:66:77-11-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.feibit_inc_co_fb56_zcw08ku1_1_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-11-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.feibit_inc_co_fb56_zcw08ku1_1_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-11-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.feibit_inc_co_fb56_zcw08ku1_1_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 13,
        SIG_MANUFACTURER: "HEIMAN",
        SIG_MODEL: "SmokeSensor-EM",
        SIG_NODE_DESC: b"\x02@\x80\x0b\x12RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1280, 1282],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_smokesensor_em_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.heiman_smokesensor_em_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_smokesensor_em_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_smokesensor_em_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_smokesensor_em_lqi",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-WarningMode"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultToneSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_smokesensor_em_default_siren_tone",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-SirenLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultSirenLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_smokesensor_em_default_siren_level",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-StrobeLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_smokesensor_em_default_strobe_level",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-Strobe"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_smokesensor_em_default_strobe",
            },
            ("siren", "00:11:22:33:44:55:66:77-1-1282"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHASiren",
                DEV_SIG_ENT_MAP_ID: "siren.heiman_smokesensor_em_siren",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 14,
        SIG_MANUFACTURER: "Heiman",
        SIG_MODEL: "CO_V16",
        SIG_NODE_DESC: b"\x02@\x84\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_co_v16_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.heiman_co_v16_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_co_v16_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_co_v16_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 15,
        SIG_MANUFACTURER: "Heiman",
        SIG_MODEL: "WarningDevice",
        SIG_NODE_DESC: b"\x01@\x8e\x0b\x12RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1027,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 9, 1280, 1282],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("select", "00:11:22:33:44:55:66:77-1-1282-WarningMode"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultToneSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_warningdevice_default_siren_tone",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-SirenLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultSirenLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_warningdevice_default_siren_level",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-StrobeLevel"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeLevelSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_warningdevice_default_strobe_level",
            },
            ("select", "00:11:22:33:44:55:66:77-1-1282-Strobe"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADefaultStrobeSelectEntity",
                DEV_SIG_ENT_MAP_ID: "select.heiman_warningdevice_default_strobe",
            },
            ("siren", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_wd"],
                DEV_SIG_ENT_MAP_CLASS: "ZHASiren",
                DEV_SIG_ENT_MAP_ID: "siren.heiman_warningdevice_siren",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_warningdevice_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.heiman_warningdevice_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_warningdevice_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_warningdevice_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 16,
        SIG_MANUFACTURER: "HiveHome.com",
        SIG_MODEL: "MOT003",
        SIG_NODE_DESC: b"\x02@\x809\x10PP\x00\x00\x00P\x00\x00",
        SIG_ENDPOINTS: {
            6: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [0, 1, 3, 32, 1024, 1026, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["6:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-6-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.hivehome_com_mot003_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-6-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.hivehome_com_mot003_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1024"): {
                DEV_SIG_CLUSTER_HANDLERS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 17,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E12 WS opal 600lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 268,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 4096, 64636],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 260,
            },
            242: {
                SIG_EP_TYPE: 97,
                DEV_SIG_EP_ID: 242,
                SIG_EP_INPUT: [33],
                SIG_EP_OUTPUT: [33],
                SIG_EP_PROFILE: 41440,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: (
                    "light.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_light"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_lqi"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 18,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 CWS opal 600lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 512,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: (
                    "light.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_light"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_lqi"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 19,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 W opal 1000lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: (
                    "light.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_light"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_lqi"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 20,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 WS opal 980lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 544,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: (
                    "light.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_light"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_lqi"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 21,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 opal 1000lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: (
                    "light.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_light"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_lqi"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 22,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI control outlet",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 266,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 64636],
                SIG_EP_OUTPUT: [5, 25, 32],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: (
                    "switch.ikea_of_sweden_tradfri_control_outlet_switch"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_control_outlet_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_control_outlet_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_control_outlet_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 23,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI motion sensor",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2128,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 6, 25, 4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_motion_sensor_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_motion_sensor_battery"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_motion_sensor_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_motion_sensor_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Motion",
                DEV_SIG_ENT_MAP_ID: (
                    "binary_sensor.ikea_of_sweden_tradfri_motion_sensor_motion"
                ),
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 24,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI on/off switch",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2080,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 32, 4096, 64636],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 258, 4096],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0019", "1:0x0102"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_on_off_switch_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_on_off_switch_battery"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_on_off_switch_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_on_off_switch_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 25,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI remote control",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2096,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 25, 4096],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_remote_control_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_remote_control_battery"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_remote_control_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_remote_control_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 26,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI signal repeater",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 8,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 9, 2821, 4096, 64636],
                SIG_EP_OUTPUT: [25, 32, 4096],
                SIG_EP_PROFILE: 260,
            },
            242: {
                SIG_EP_TYPE: 97,
                DEV_SIG_EP_ID: 242,
                SIG_EP_INPUT: [33],
                SIG_EP_OUTPUT: [33],
                SIG_EP_PROFILE: 41440,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_signal_repeater_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_signal_repeater_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_signal_repeater_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 27,
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI wireless dimmer",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 4096],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.ikea_of_sweden_tradfri_wireless_dimmer_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_wireless_dimmer_battery"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.ikea_of_sweden_tradfri_wireless_dimmer_rssi"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_wireless_dimmer_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 28,
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45852",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 260,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821],
                SIG_EP_OUTPUT: [3, 6, 8],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019", "2:0x0006", "2:0x0008"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45852_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.jasco_products_45852_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 29,
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45856",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 1794, 2821],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 259,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821],
                SIG_EP_OUTPUT: [3, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45856_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.jasco_products_45856_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 30,
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45857",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 260,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 3, 2821],
                SIG_EP_OUTPUT: [3, 6, 8],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019", "2:0x0006", "2:0x0008"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45857_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.jasco_products_45857_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 31,
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-610-MP-1.3",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 8, 32, 1026, 1027, 2821, 64513, 64514],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.keen_home_inc_sv02_610_mp_1_3_identify",
            },
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_610_mp_1_3_keen_vent",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CLUSTER_HANDLERS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 32,
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-612-MP-1.2",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 8, 32, 1026, 1027, 2821, 64513, 64514],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.keen_home_inc_sv02_612_mp_1_2_identify",
            },
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_612_mp_1_2_keen_vent",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CLUSTER_HANDLERS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 33,
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-612-MP-1.3",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 8, 32, 1026, 1027, 2821, 64513, 64514],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.keen_home_inc_sv02_612_mp_1_3_identify",
            },
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_612_mp_1_3_keen_vent",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CLUSTER_HANDLERS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 34,
        SIG_MANUFACTURER: "King Of Fans,  Inc.",
        SIG_MODEL: "HBUniversalCFRemote",
        SIG_NODE_DESC: b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 514],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.king_of_fans_inc_hbuniversalcfremote_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: (
                    "button.king_of_fans_inc_hbuniversalcfremote_identify"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.king_of_fans_inc_hbuniversalcfremote_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.king_of_fans_inc_hbuniversalcfremote_lqi",
            },
            ("fan", "00:11:22:33:44:55:66:77-1-514"): {
                DEV_SIG_CLUSTER_HANDLERS: ["fan"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaFan",
                DEV_SIG_ENT_MAP_ID: "fan.king_of_fans_inc_hbuniversalcfremote_fan",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 35,
        SIG_MANUFACTURER: "LDS",
        SIG_MODEL: "ZBT-CCTSwitch-D0001",
        SIG_NODE_DESC: b"\x02@\x80h\x11RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2048,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4096, 64769],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0019", "1:0x0300"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lds_zbt_cctswitch_d0001_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lds_zbt_cctswitch_d0001_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lds_zbt_cctswitch_d0001_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lds_zbt_cctswitch_d0001_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 36,
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "A19 RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_a19_rgbw_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.ledvance_a19_rgbw_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_a19_rgbw_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_a19_rgbw_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 37,
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "FLEX RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_flex_rgbw_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.ledvance_flex_rgbw_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_flex_rgbw_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_flex_rgbw_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 38,
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "PLUG",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2821, 64513, 64520],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.ledvance_plug_switch",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.ledvance_plug_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_plug_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_plug_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 39,
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "RT RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_rt_rgbw_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.ledvance_rt_rgbw_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_rt_rgbw_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.ledvance_rt_rgbw_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 40,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.plug.maus01",
        SIG_NODE_DESC: b"\x01@\x8e_\x11\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 2, 3, 4, 5, 6, 10, 16, 2820],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 9,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [12],
                SIG_EP_OUTPUT: [4, 12],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 83,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [12],
                SIG_EP_OUTPUT: [12],
                SIG_EP_PROFILE: 260,
            },
            100: {
                SIG_EP_TYPE: 263,
                DEV_SIG_EP_ID: 100,
                SIG_EP_INPUT: [15],
                SIG_EP_OUTPUT: [4, 15],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.lumi_lumi_plug_maus01_switch",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_device_temperature",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_plug_maus01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-100-15"): {
                DEV_SIG_CLUSTER_HANDLERS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_plug_maus01_binary_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_summation_delivered",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 41,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.relay.c2acn01",
        SIG_NODE_DESC: b"\x01@\x8e7\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 2, 3, 4, 5, 6, 10, 12, 16, 2820],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [4, 5, 6, 16],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_relay_c2acn01_light",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_device_temperature",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_relay_c2acn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_lqi",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_relay_c2acn01_light_2",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 42,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b186acn01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 18, 25, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 18, 25, 65535],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 24323,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 12, 18],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b186acn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b186acn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b186acn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b186acn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 43,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b286acn01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 18, 25, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 18, 25, 65535],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 24323,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 12, 18],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b286acn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286acn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286acn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286acn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 44,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b286opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 261,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6, 8, 768],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            3: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            4: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            5: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            6: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b286opcn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286opcn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286opcn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286opcn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 45,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b486opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 261,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6, 8, 768],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 259,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3],
                SIG_EP_OUTPUT: [3, 6],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            4: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            5: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
            6: {
                SIG_EP_TYPE: -1,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: -1,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b486opcn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b486opcn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b486opcn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b486opcn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 46,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b686opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 261,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6, 8, 768],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b686opcn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 47,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b686opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 261,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6, 8, 768],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 259,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3],
                SIG_EP_OUTPUT: [3, 6],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: None,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: None,
            },
            4: {
                SIG_EP_TYPE: None,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: None,
            },
            5: {
                SIG_EP_TYPE: None,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: None,
            },
            6: {
                SIG_EP_TYPE: None,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: None,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_remote_b686opcn01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b686opcn01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 48,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["8:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_light",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_opening",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 49,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6, 11, 17],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["8:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_light",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_opening",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 50,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6, 17],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["8:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_light",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-8-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_router_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_opening",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 51,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sen_ill.mgl01",
        SIG_NODE_DESC: b"\x02@\x84n\x12\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 262,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1024],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sen_ill_mgl01_battery",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sen_ill_mgl01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CLUSTER_HANDLERS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sen_ill_mgl01_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sen_ill_mgl01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sen_ill_mgl01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 52,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_86sw1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 18, 25, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 18, 25, 65535],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 24323,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 12, 18],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_86sw1_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_86sw1_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_86sw1_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_86sw1_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 53,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_cube.aqgl01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 28417,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 25],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 18, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 28418,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3, 18],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 28419,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [3, 12],
                SIG_EP_OUTPUT: [3, 4, 5, 12],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_cube_aqgl01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_cube_aqgl01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_cube_aqgl01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_cube_aqgl01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 54,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_ht",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 25, 1026, 1029, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 18, 25, 65535],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 24323,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [3],
                SIG_EP_OUTPUT: [3, 4, 5, 12],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_ht_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                DEV_SIG_CLUSTER_HANDLERS: ["humidity"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_humidity",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 55,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_magnet",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2128,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 25, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_magnet_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_magnet_opening",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 56,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_magnet.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 65535],
                SIG_EP_OUTPUT: [0, 4, 6, 65535],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_magnet_aq2_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_aq2_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_aq2_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_aq2_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_magnet_aq2_opening",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 57,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_motion.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 263,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1024, 1030, 1280, 65535],
                SIG_EP_OUTPUT: [0, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1030"): {
                DEV_SIG_CLUSTER_HANDLERS: ["occupancy"],
                DEV_SIG_ENT_MAP_CLASS: "Occupancy",
                DEV_SIG_ENT_MAP_ID: (
                    "binary_sensor.lumi_lumi_sensor_motion_aq2_occupancy"
                ),
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_motion_aq2_motion",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_motion_aq2_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CLUSTER_HANDLERS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.lumi_lumi_sensor_motion_aq2_device_temperature"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 58,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_smoke",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 12, 18, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_smoke_smoke",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_smoke_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_smoke_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.lumi_lumi_sensor_smoke_device_temperature"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_smoke_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_smoke_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 59,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [0, 4, 5, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_switch_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 60,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 65535],
                SIG_EP_OUTPUT: [0, 4, 6, 65535],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq2_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq2_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq2_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 61,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch.aq3",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 18],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq3_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq3_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq3_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 62,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_wleak.aq1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 2, 3, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_wleak_aq1_iaszone",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.lumi_lumi_sensor_wleak_aq1_device_temperature"
                ),
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_sensor_wleak_aq1_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_wleak_aq1_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_wleak_aq1_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_wleak_aq1_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 63,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.vibration.aq1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.DOOR_LOCK,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Ota.cluster_id,
                    DoorLock.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    Ota.cluster_id,
                    DoorLock.cluster_id,
                ],
            },
            2: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: 0x5F02,
                INPUT_CLUSTERS: [Identify.cluster_id, MultistateInput.cluster_id],
                OUTPUT_CLUSTERS: [
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    MultistateInput.cluster_id,
                ],
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0019", "2:0x0005"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_vibration_aq1_vibration",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_vibration_aq1_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_vibration_aq1_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_vibration_aq1_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_vibration_aq1_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["device_temperature"],
                DEV_SIG_ENT_MAP_CLASS: "DeviceTemperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_vibration_aq1_device_temperature",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 64,
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.weather",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1026, 1027, 1029, 65535],
                SIG_EP_OUTPUT: [0, 4, 65535],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.lumi_lumi_weather_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CLUSTER_HANDLERS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                DEV_SIG_CLUSTER_HANDLERS: ["humidity"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_humidity",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 65,
        SIG_MANUFACTURER: "NYCE",
        SIG_MODEL: "3010",
        SIG_NODE_DESC: b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1280],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.nyce_3010_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.nyce_3010_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3010_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3010_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3010_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 66,
        SIG_MANUFACTURER: "NYCE",
        SIG_MODEL: "3014",
        SIG_NODE_DESC: b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1280],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.nyce_3014_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.nyce_3014_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3014_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3014_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3014_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 67,
        SIG_MANUFACTURER: None,
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x10@\x0f5\x11Y=\x00@\x00=\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 5,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [10, 25],
                SIG_EP_OUTPUT: [1280],
                SIG_EP_PROFILE: 260,
            },
            242: {
                SIG_EP_TYPE: 100,
                DEV_SIG_EP_ID: 242,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [33],
                SIG_EP_PROFILE: 41440,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {},
    },
    {
        DEV_SIG_DEV_NO: 68,
        SIG_MANUFACTURER: None,
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x00@\x8f\xcd\xabR\x80\x00\x00\x00\x80\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 48879,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [1280],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {},
    },
    {
        DEV_SIG_DEV_NO: 69,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY A19 RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["3:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "light_color", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_a19_rgbw_light",
            },
            ("button", "00:11:22:33:44:55:66:77-3-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.osram_lightify_a19_rgbw_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_a19_rgbw_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_a19_rgbw_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 70,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY Dimming Switch",
        SIG_NODE_DESC: b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 2821],
                SIG_EP_OUTPUT: [3, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.osram_lightify_dimming_switch_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_dimming_switch_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_dimming_switch_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_dimming_switch_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 71,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY Flex RGBW",
        SIG_NODE_DESC: b"\x19@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["3:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "light_color", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_flex_rgbw_light",
            },
            ("button", "00:11:22:33:44:55:66:77-3-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.osram_lightify_flex_rgbw_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_flex_rgbw_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_flex_rgbw_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 72,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY RT Tunable White",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2820, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["3:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "light_color", "level"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_rt_tunable_white_light",
            },
            ("button", "00:11:22:33:44:55:66:77-3-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.osram_lightify_rt_tunable_white_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_active_power"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_apparent_power"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_rms_current"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_rms_voltage"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_ac_frequency"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.osram_lightify_rt_tunable_white_power_factor"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 73,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "Plug 01",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 16,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2820, 4096, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 49246,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["3:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.osram_plug_01_switch",
            },
            ("button", "00:11:22:33:44:55:66:77-3-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.osram_plug_01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 74,
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "Switch 4x-LIGHTIFY",
        SIG_NODE_DESC: b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 32, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 25, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
            4: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [0, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
            5: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [0, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
            6: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [0, 4096, 64768],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 768, 4096],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [
            "1:0x0005",
            "1:0x0006",
            "1:0x0008",
            "1:0x0019",
            "1:0x0300",
            "2:0x0005",
            "2:0x0006",
            "2:0x0008",
            "2:0x0300",
            "3:0x0005",
            "3:0x0006",
            "3:0x0008",
            "3:0x0300",
            "4:0x0005",
            "4:0x0006",
            "4:0x0008",
            "4:0x0300",
            "5:0x0005",
            "5:0x0006",
            "5:0x0008",
            "5:0x0300",
            "6:0x0005",
            "6:0x0006",
            "6:0x0008",
            "6:0x0300",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_switch_4x_lightify_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_switch_4x_lightify_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_switch_4x_lightify_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 75,
        SIG_MANUFACTURER: "Philips",
        SIG_MODEL: "RWL020",
        SIG_NODE_DESC: b"\x02@\x80\x0b\x10G-\x00\x00\x00-\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2096,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 6, 8],
                SIG_EP_PROFILE: 49246,
            },
            2: {
                SIG_EP_TYPE: 12,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 1, 3, 15, 64512],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0006", "1:0x0008", "2:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.philips_rwl020_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.philips_rwl020_lqi",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-2-15"): {
                DEV_SIG_CLUSTER_HANDLERS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.philips_rwl020_binary_input",
            },
            ("button", "00:11:22:33:44:55:66:77-2-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.philips_rwl020_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.philips_rwl020_battery",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 76,
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "button",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_button_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.samjin_button_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 77,
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "multi",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 64514],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_multi_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.samjin_multi_identify",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-64514"): {
                DEV_SIG_CLUSTER_HANDLERS: ["accelerometer"],
                DEV_SIG_ENT_MAP_CLASS: "Accelerometer",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_multi_accelerometer",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 78,
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "water",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_water_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.samjin_water_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 79,
        SIG_MANUFACTURER: "Securifi Ltd.",
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x01@\x8e\x02\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 0,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 2820, 2821],
                SIG_EP_OUTPUT: [0, 1, 3, 4, 5, 6, 25, 2820, 2821],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0005", "1:0x0006", "1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.securifi_ltd_unk_model_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_lqi",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.securifi_ltd_unk_model_switch",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 80,
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-DWS04N_SF",
        SIG_NODE_DESC: b"\x02@\x801\x11R\xff\x00\x00\x00\xff\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.sercomm_corp_sz_dws04n_sf_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sercomm_corp_sz_dws04n_sf_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 81,
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-ESW01",
        SIG_NODE_DESC: b"\x01@\x8e1\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 1794, 2820, 2821],
                SIG_EP_OUTPUT: [3, 10, 25, 2821],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 259,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019", "2:0x0006"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.sercomm_corp_sz_esw01_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sercomm_corp_sz_esw01_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 82,
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-PIR04",
        SIG_NODE_DESC: b"\x02@\x801\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1024, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.sercomm_corp_sz_pir04_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sercomm_corp_sz_pir04_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CLUSTER_HANDLERS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 83,
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "RM3250ZB",
        SIG_NODE_DESC: b"\x11@\x8e\x9c\x11G+\x00\x00*+\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2820, 2821, 65281],
                SIG_EP_OUTPUT: [3, 4, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sinope_technologies_rm3250zb_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.sinope_technologies_rm3250zb_apparent_power"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_lqi",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.sinope_technologies_rm3250zb_switch",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 84,
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "TH1123ZB",
        SIG_NODE_DESC: b"\x12@\x8c\x9c\x11G+\x00\x00\x00+\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 513, 516, 1026, 2820, 2821, 65281],
                SIG_EP_OUTPUT: [25, 65281],
                SIG_EP_PROFILE: 260,
            },
            196: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 196,
                SIG_EP_INPUT: [1],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49757,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sinope_technologies_th1123zb_identify",
            },
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: [
                    "thermostat",
                    "sinope_manufacturer_specific",
                ],
                DEV_SIG_ENT_MAP_CLASS: "SinopeTechnologiesThermostat",
                DEV_SIG_ENT_MAP_ID: "climate.sinope_technologies_th1123zb_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.sinope_technologies_th1123zb_apparent_power"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CLUSTER_HANDLERS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "SinopeHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_hvac_action",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 85,
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "TH1124ZB",
        SIG_NODE_DESC: b"\x11@\x8e\x9c\x11G+\x00\x00\x00+\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 513, 516, 1026, 2820, 2821, 65281],
                SIG_EP_OUTPUT: [25, 65281],
                SIG_EP_PROFILE: 260,
            },
            196: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 196,
                SIG_EP_INPUT: [1],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49757,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sinope_technologies_th1124zb_identify",
            },
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: [
                    "thermostat",
                    "sinope_manufacturer_specific",
                ],
                DEV_SIG_ENT_MAP_CLASS: "SinopeTechnologiesThermostat",
                DEV_SIG_ENT_MAP_ID: "climate.sinope_technologies_th1124zb_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: (
                    "sensor.sinope_technologies_th1124zb_apparent_power"
                ),
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CLUSTER_HANDLERS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "SinopeHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_hvac_action",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 86,
        SIG_MANUFACTURER: "SmartThings",
        SIG_MODEL: "outletv4",
        SIG_NODE_DESC: b"\x01@\x8e\n\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 9, 15, 2820],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-15"): {
                DEV_SIG_CLUSTER_HANDLERS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.smartthings_outletv4_binary_input",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.smartthings_outletv4_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_active_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-ac_frequency"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementFrequency",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_ac_frequency",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-power_factor"): {
                DEV_SIG_CLUSTER_HANDLERS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementPowerFactor",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_power_factor",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_lqi",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.smartthings_outletv4_switch",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 87,
        SIG_MANUFACTURER: "SmartThings",
        SIG_MODEL: "tagv4",
        SIG_NODE_DESC: b"\x02@\x80\n\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 32768,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 15, 32],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("device_tracker", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADeviceScannerEntity",
                DEV_SIG_ENT_MAP_ID: "device_tracker.smartthings_tagv4_device_scanner",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-15"): {
                DEV_SIG_CLUSTER_HANDLERS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.smartthings_tagv4_binary_input",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.smartthings_tagv4_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_tagv4_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_tagv4_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 88,
        SIG_MANUFACTURER: "Third Reality, Inc",
        SIG_MODEL: "3RSS007Z",
        SIG_NODE_DESC: b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 25],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.third_reality_inc_3rss007z_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss007z_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss007z_lqi",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.third_reality_inc_3rss007z_switch",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 89,
        SIG_MANUFACTURER: "Third Reality, Inc",
        SIG_MODEL: "3RSS008Z",
        SIG_NODE_DESC: b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 25],
                SIG_EP_OUTPUT: [1],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.third_reality_inc_3rss008z_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss008z_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss008z_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss008z_lqi",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.third_reality_inc_3rss008z_switch",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 90,
        SIG_MANUFACTURER: "Visonic",
        SIG_MODEL: "MCT-340 E",
        SIG_NODE_DESC: b"\x02@\x80\x11\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.visonic_mct_340_e_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.visonic_mct_340_e_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 91,
        SIG_MANUFACTURER: "Zen Within",
        SIG_MODEL: "Zen-01",
        SIG_NODE_DESC: b"\x02@\x80X\x11R\x80\x00\x00\x00\x80\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 32, 513, 514, 516, 2821],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.zen_within_zen_01_identify",
            },
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["thermostat", "fan"],
                DEV_SIG_ENT_MAP_CLASS: "ZenWithinThermostat",
                DEV_SIG_ENT_MAP_ID: "climate.zen_within_zen_01_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_lqi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CLUSTER_HANDLERS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "ThermostatHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_hvac_action",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 92,
        SIG_MANUFACTURER: "_TYZB01_ns1ndbww",
        SIG_MODEL: "TS0004",
        SIG_NODE_DESC: b"\x01@\x8e\x02\x10R\x00\x02\x00,\x00\x02\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 4, 5, 6, 10],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [4, 5, 6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
            3: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [4, 5, 6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
            4: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 4,
                SIG_EP_INPUT: [4, 5, 6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_light",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.tyzb01_ns1ndbww_ts0004_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.tyzb01_ns1ndbww_ts0004_lqi",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_light_2",
            },
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_light_3",
            },
            ("light", "00:11:22:33:44:55:66:77-4"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_light_4",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 93,
        SIG_MANUFACTURER: "netvox",
        SIG_MODEL: "Z308E3ED",
        SIG_NODE_DESC: b"\x02@\x80\x9f\x10RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 21, 32, 1280, 2821],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CLUSTER_HANDLERS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.netvox_z308e3ed_iaszone",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.netvox_z308e3ed_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.netvox_z308e3ed_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.netvox_z308e3ed_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.netvox_z308e3ed_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 94,
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "E11-G13",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "MinTransitionLight",
                DEV_SIG_ENT_MAP_ID: "light.sengled_e11_g13_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sengled_e11_g13_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 95,
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "E12-N14",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level"],
                DEV_SIG_ENT_MAP_CLASS: "MinTransitionLight",
                DEV_SIG_ENT_MAP_ID: "light.sengled_e12_n14_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sengled_e12_n14_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 96,
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "Z01-A19NAE26",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off", "level", "light_color"],
                DEV_SIG_ENT_MAP_CLASS: "MinTransitionLight",
                DEV_SIG_ENT_MAP_ID: "light.sengled_z01_a19nae26_light",
            },
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.sengled_z01_a19nae26_identify",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_instantaneous_demand",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CLUSTER_HANDLERS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 97,
        SIG_MANUFACTURER: "unk_manufacturer",
        SIG_MODEL: "unk_model",
        SIG_NODE_DESC: b"\x01@\x8e\x10\x11RR\x00\x00\x00R\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 512,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 10, 21, 256, 64544, 64545],
                SIG_EP_OUTPUT: [3, 64544],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("button", "00:11:22:33:44:55:66:77-1-3"): {
                DEV_SIG_CLUSTER_HANDLERS: ["identify"],
                DEV_SIG_ENT_MAP_CLASS: "ZHAIdentifyButton",
                DEV_SIG_ENT_MAP_ID: "button.unk_manufacturer_unk_model_identify",
            },
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["level", "on_off", "shade"],
                DEV_SIG_ENT_MAP_CLASS: "Shade",
                DEV_SIG_ENT_MAP_ID: "cover.unk_manufacturer_unk_model_shade",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.unk_manufacturer_unk_model_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.unk_manufacturer_unk_model_lqi",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 98,
        SIG_MANUFACTURER: "Digi",
        SIG_MODEL: "XBee3",
        SIG_NODE_DESC: b"\x01@\x8e\x1e\x10R\xff\x00\x00,\xff\x00\x00",
        SIG_ENDPOINTS: {
            208: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 208,
                SIG_EP_INPUT: [6, 12],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            209: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 209,
                SIG_EP_INPUT: [6, 12],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            210: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 210,
                SIG_EP_INPUT: [6, 12],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            211: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 211,
                SIG_EP_INPUT: [6, 12],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            212: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 212,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            213: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 213,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            214: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 214,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            215: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 215,
                SIG_EP_INPUT: [6, 12],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            216: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 216,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            217: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 217,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            218: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 218,
                SIG_EP_INPUT: [6, 13],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            219: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 219,
                SIG_EP_INPUT: [6, 13],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            220: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 220,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            221: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 221,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            222: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 222,
                SIG_EP_INPUT: [6],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 49413,
            },
            232: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 232,
                SIG_EP_INPUT: [17, 146],
                SIG_EP_OUTPUT: [8, 17],
                SIG_EP_PROFILE: 49413,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: ["232:0x0008"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-208-12"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_analog_input",
            },
            ("switch", "00:11:22:33:44:55:66:77-208-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch",
            },
            ("sensor", "00:11:22:33:44:55:66:77-209-12"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_analog_input_2",
            },
            ("switch", "00:11:22:33:44:55:66:77-209-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_2",
            },
            ("sensor", "00:11:22:33:44:55:66:77-210-12"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_analog_input_3",
            },
            ("switch", "00:11:22:33:44:55:66:77-210-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_3",
            },
            ("sensor", "00:11:22:33:44:55:66:77-211-12"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_analog_input_4",
            },
            ("switch", "00:11:22:33:44:55:66:77-211-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_4",
            },
            ("switch", "00:11:22:33:44:55:66:77-212-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_5",
            },
            ("switch", "00:11:22:33:44:55:66:77-213-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_6",
            },
            ("switch", "00:11:22:33:44:55:66:77-214-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_7",
            },
            ("sensor", "00:11:22:33:44:55:66:77-215-12"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_analog_input_5",
            },
            ("switch", "00:11:22:33:44:55:66:77-215-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_8",
            },
            ("switch", "00:11:22:33:44:55:66:77-216-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_9",
            },
            ("switch", "00:11:22:33:44:55:66:77-217-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_10",
            },
            ("number", "00:11:22:33:44:55:66:77-218-13"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_output"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaNumber",
                DEV_SIG_ENT_MAP_ID: "number.digi_xbee3_number",
            },
            ("switch", "00:11:22:33:44:55:66:77-218-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_11",
            },
            ("switch", "00:11:22:33:44:55:66:77-219-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_12",
            },
            ("number", "00:11:22:33:44:55:66:77-219-13"): {
                DEV_SIG_CLUSTER_HANDLERS: ["analog_output"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaNumber",
                DEV_SIG_ENT_MAP_ID: "number.digi_xbee3_number_2",
            },
            ("switch", "00:11:22:33:44:55:66:77-220-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_13",
            },
            ("switch", "00:11:22:33:44:55:66:77-221-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_14",
            },
            ("switch", "00:11:22:33:44:55:66:77-222-6"): {
                DEV_SIG_CLUSTER_HANDLERS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_switch_15",
            },
        },
    },
    {
        DEV_SIG_DEV_NO: 99,
        SIG_MANUFACTURER: "efektalab.ru",
        SIG_MODEL: "EFEKTA_PWS",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 12,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 1026, 1032],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_EVT_CLUSTER_HANDLERS: [],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CLUSTER_HANDLERS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_battery",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1032"): {
                DEV_SIG_CLUSTER_HANDLERS: ["soil_moisture"],
                DEV_SIG_ENT_MAP_CLASS: "SoilMoisture",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_soil_moisture",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CLUSTER_HANDLERS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-rssi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "RSSISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_rssi",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-0-lqi"): {
                DEV_SIG_CLUSTER_HANDLERS: ["basic"],
                DEV_SIG_ENT_MAP_CLASS: "LQISensor",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_lqi",
            },
        },
    },
]
