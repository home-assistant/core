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

DEV_SIG_CHANNELS = "channels"
DEV_SIG_DEV_NO = "device_no"
DEV_SIG_ENTITIES = "entities"
DEV_SIG_ENT_MAP = "entity_map"
DEV_SIG_ENT_MAP_CLASS = "entity_class"
DEV_SIG_ENT_MAP_ID = "entity_id"
DEV_SIG_EP_ID = "endpoint_id"
DEV_SIG_EVT_CHANNELS = "event_channels"
DEV_SIG_ZHA_QUIRK = "zha_quirk"

DEVICES = [
    {
        DEV_SIG_DEV_NO: 0,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2080,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4096, 64716],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 4096, 64716],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008"],
        SIG_MANUFACTURER: "ADUROLIGHT",
        SIG_MODEL: "Adurolight_NCC",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "AdurolightNCC",
    },
    {
        DEV_SIG_DEV_NO: 1,
        SIG_ENDPOINTS: {
            5: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 5,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.bosch_isw_zpr1_wp13_77665544_ias_zone",
            "sensor.bosch_isw_zpr1_wp13_77665544_power",
            "sensor.bosch_isw_zpr1_wp13_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-5-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.bosch_isw_zpr1_wp13_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-5-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.bosch_isw_zpr1_wp13_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["5:0x0019"],
        SIG_MANUFACTURER: "Bosch",
        SIG_MODEL: "ISW-ZPR1-WP13",
        SIG_NODE_DESC: b"\x02@\x08\x00\x00l\x00\x00\x00\x00\x00\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 2,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 2821],
                SIG_EP_OUTPUT: [3, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.centralite_3130_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3130_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3130",
        SIG_NODE_DESC: b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLite3130",
    },
    {
        DEV_SIG_DEV_NO: 3,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 1794, 2820, 2821, 64515],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.centralite_3210_l_77665544_electrical_measurement",
            "sensor.centralite_3210_l_77665544_electrical_measurement_apparent_power",
            "sensor.centralite_3210_l_77665544_electrical_measurement_apparent_power",
            "sensor.centralite_3210_l_77665544_electrical_measurement_rms_current",
            "sensor.centralite_3210_l_77665544_electrical_measurement_rms_voltage",
            "sensor.centralite_3210_l_77665544_smartenergy_metering",
            "sensor.centralite_3210_l_77665544_smartenergy_metering_summation_delivered",
            "switch.centralite_3210_l_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.centralite_3210_l_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_smartenergy_metering_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3210_l_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3210-L",
        SIG_NODE_DESC: b"\x01@\x8eN\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 4,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 770,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 2821, 64581],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.centralite_3310_s_77665544_manufacturer_specific",
            "sensor.centralite_3310_s_77665544_power",
            "sensor.centralite_3310_s_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-64581"): {
                DEV_SIG_CHANNELS: ["manufacturer_specific"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3310_s_77665544_manufacturer_specific",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3310-S",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLite3310S",
    },
    {
        DEV_SIG_DEV_NO: 5,
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
        DEV_SIG_ENTITIES: [
            "binary_sensor.centralite_3315_s_77665544_ias_zone",
            "sensor.centralite_3315_s_77665544_power",
            "sensor.centralite_3315_s_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3315_s_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3315_s_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3315-S",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLiteIASSensor",
    },
    {
        DEV_SIG_DEV_NO: 6,
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
        DEV_SIG_ENTITIES: [
            "binary_sensor.centralite_3320_l_77665544_ias_zone",
            "sensor.centralite_3320_l_77665544_power",
            "sensor.centralite_3320_l_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3320_l_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3320_l_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3320-L",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLiteIASSensor",
    },
    {
        DEV_SIG_DEV_NO: 7,
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
        DEV_SIG_ENTITIES: [
            "binary_sensor.centralite_3326_l_77665544_ias_zone",
            "sensor.centralite_3326_l_77665544_power",
            "sensor.centralite_3326_l_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_3326_l_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_3326_l_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "3326-L",
        SIG_NODE_DESC: b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLiteMotionSensor",
    },
    {
        DEV_SIG_DEV_NO: 8,
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
        DEV_SIG_ENTITIES: [
            "binary_sensor.centralite_motion_sensor_a_77665544_ias_zone",
            "binary_sensor.centralite_motion_sensor_a_77665544_occupancy",
            "sensor.centralite_motion_sensor_a_77665544_power",
            "sensor.centralite_motion_sensor_a_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.centralite_motion_sensor_a_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_motion_sensor_a_77665544_ias_zone",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-2-1030"): {
                DEV_SIG_CHANNELS: ["occupancy"],
                DEV_SIG_ENT_MAP_CLASS: "Occupancy",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.centralite_motion_sensor_a_77665544_occupancy",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "CentraLite",
        SIG_MODEL: "Motion Sensor-A",
        SIG_NODE_DESC: b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLite3305S",
    },
    {
        DEV_SIG_DEV_NO: 9,
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
        DEV_SIG_ENTITIES: [
            "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering",
            "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering_summation_delivered",
            "switch.climaxtechnology_psmp5_00_00_02_02tc_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.climaxtechnology_psmp5_00_00_02_02tc_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["4:0x0019"],
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "PSMP5_00.00.02.02TC",
        SIG_NODE_DESC: b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 10,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 1280, 1282],
                SIG_EP_OUTPUT: [0],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.climaxtechnology_sd8sc_00_00_03_12tc_77665544_ias_zone"
        ],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.climaxtechnology_sd8sc_00_00_03_12tc_77665544_ias_zone",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "SD8SC_00.00.03.12TC",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 11,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 1280],
                SIG_EP_OUTPUT: [0],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.climaxtechnology_ws15_00_00_03_03tc_77665544_ias_zone"
        ],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.climaxtechnology_ws15_00_00_03_03tc_77665544_ias_zone",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "ClimaxTechnology",
        SIG_MODEL: "WS15_00.00.03.03TC",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 12,
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
        DEV_SIG_ENTITIES: [
            "light.feibit_inc_co_fb56_zcw08ku1_1_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-11"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.feibit_inc_co_fb56_zcw08ku1_1_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "Feibit Inc co.",
        SIG_MODEL: "FB56-ZCW08KU1.1",
        SIG_NODE_DESC: b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 13,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1280, 1282],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.heiman_smokesensor_em_77665544_ias_zone",
            "sensor.heiman_smokesensor_em_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.heiman_smokesensor_em_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_smokesensor_em_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "HEIMAN",
        SIG_MODEL: "SmokeSensor-EM",
        SIG_NODE_DESC: b"\x02@\x80\x0b\x12RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 14,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["binary_sensor.heiman_co_v16_77665544_ias_zone"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_co_v16_77665544_ias_zone",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Heiman",
        SIG_MODEL: "CO_V16",
        SIG_NODE_DESC: b"\x02@\x84\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
    },
    {
        DEV_SIG_DEV_NO: 15,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1027,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 9, 1280, 1282],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["binary_sensor.heiman_warningdevice_77665544_ias_zone"],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.heiman_warningdevice_77665544_ias_zone",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Heiman",
        SIG_MODEL: "WarningDevice",
        SIG_NODE_DESC: b"\x01@\x8e\x0b\x12RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 16,
        SIG_ENDPOINTS: {
            6: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 6,
                SIG_EP_INPUT: [0, 1, 3, 32, 1024, 1026, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.hivehome_com_mot003_77665544_ias_zone",
            "sensor.hivehome_com_mot003_77665544_illuminance",
            "sensor.hivehome_com_mot003_77665544_power",
            "sensor.hivehome_com_mot003_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-6-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1024"): {
                DEV_SIG_CHANNELS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_77665544_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.hivehome_com_mot003_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-6-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.hivehome_com_mot003_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["6:0x0019"],
        SIG_MANUFACTURER: "HiveHome.com",
        SIG_MODEL: "MOT003",
        SIG_NODE_DESC: b"\x02@\x809\x10PP\x00\x00\x00P\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MOT003",
    },
    {
        DEV_SIG_DEV_NO: 17,
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
        DEV_SIG_ENTITIES: [
            "light.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E12 WS opal 600lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 18,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 512,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 CWS opal 600lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 19,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_77665544_level_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_77665544_level_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 W opal 1000lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 20,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 544,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 WS opal 980lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 21,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 2821, 4096],
                SIG_EP_OUTPUT: [5, 25, 32, 4096],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_77665544_level_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_77665544_level_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI bulb E26 opal 1000lm",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 22,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 266,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 64636],
                SIG_EP_OUTPUT: [5, 25, 32],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "switch.ikea_of_sweden_tradfri_control_outlet_77665544_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.ikea_of_sweden_tradfri_control_outlet_77665544_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI control outlet",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "TradfriPlug",
    },
    {
        DEV_SIG_DEV_NO: 23,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2128,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 6, 25, 4096],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_on_off",
            "sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Motion",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI motion sensor",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "IkeaTradfriMotion",
    },
    {
        DEV_SIG_DEV_NO: 24,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2080,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 32, 4096, 64636],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 258, 4096],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.ikea_of_sweden_tradfri_on_off_switch_77665544_power"
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_on_off_switch_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0019", "1:0x0102"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI on/off switch",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00,R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "IkeaTradfriRemote2Btn",
    },
    {
        DEV_SIG_DEV_NO: 25,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2096,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 5, 6, 8, 25, 4096],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.ikea_of_sweden_tradfri_remote_control_77665544_power"
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_remote_control_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI remote control",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "IkeaTradfriRemote",
    },
    {
        DEV_SIG_DEV_NO: 26,
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
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI signal repeater",
        SIG_NODE_DESC: b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 27,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2064,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 9, 2821, 4096],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 4096],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.ikea_of_sweden_tradfri_wireless_dimmer_77665544_power"
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.ikea_of_sweden_tradfri_wireless_dimmer_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "IKEA of Sweden",
        SIG_MODEL: "TRADFRI wireless dimmer",
        SIG_NODE_DESC: b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 28,
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
        DEV_SIG_ENTITIES: [
            "light.jasco_products_45852_77665544_level_on_off",
            "sensor.jasco_products_45852_77665544_smartenergy_metering",
            "sensor.jasco_products_45852_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45852_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45852_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019", "2:0x0006", "2:0x0008"],
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45852",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 29,
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
        DEV_SIG_ENTITIES: [
            "light.jasco_products_45856_77665544_on_off",
            "sensor.jasco_products_45856_77665544_smartenergy_metering",
            "sensor.jasco_products_45856_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45856_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45856_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019", "2:0x0006"],
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45856",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 30,
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
        DEV_SIG_ENTITIES: [
            "light.jasco_products_45857_77665544_level_on_off",
            "sensor.jasco_products_45857_77665544_smartenergy_metering",
            "sensor.jasco_products_45857_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.jasco_products_45857_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.jasco_products_45857_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019", "2:0x0006", "2:0x0008"],
        SIG_MANUFACTURER: "Jasco Products",
        SIG_MODEL: "45857",
        SIG_NODE_DESC: b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 31,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [
                    0,
                    1,
                    3,
                    4,
                    5,
                    6,
                    8,
                    32,
                    1026,
                    1027,
                    2821,
                    64513,
                    64514,
                ],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "cover.keen_home_inc_sv02_610_mp_1_3_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_power",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_610_mp_1_3_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CHANNELS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_pressure",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-610-MP-1.3",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 32,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [
                    0,
                    1,
                    3,
                    4,
                    5,
                    6,
                    8,
                    32,
                    1026,
                    1027,
                    2821,
                    64513,
                    64514,
                ],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "cover.keen_home_inc_sv02_612_mp_1_2_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_pressure",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_612_mp_1_2_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CHANNELS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_pressure",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-612-MP-1.2",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 33,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 3,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [
                    0,
                    1,
                    3,
                    4,
                    5,
                    6,
                    8,
                    32,
                    1026,
                    1027,
                    2821,
                    64513,
                    64514,
                ],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "cover.keen_home_inc_sv02_612_mp_1_3_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "KeenVent",
                DEV_SIG_ENT_MAP_ID: "cover.keen_home_inc_sv02_612_mp_1_3_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CHANNELS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_pressure",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Keen Home Inc",
        SIG_MODEL: "SV02-612-MP-1.3",
        SIG_NODE_DESC: b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "KeenHomeSmartVent",
    },
    {
        DEV_SIG_DEV_NO: 34,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 514],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "fan.king_of_fans_inc_hbuniversalcfremote_77665544_fan",
            "light.king_of_fans_inc_hbuniversalcfremote_77665544_level_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.king_of_fans_inc_hbuniversalcfremote_77665544_level_on_off",
            },
            ("fan", "00:11:22:33:44:55:66:77-1-514"): {
                DEV_SIG_CHANNELS: ["fan"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaFan",
                DEV_SIG_ENT_MAP_ID: "fan.king_of_fans_inc_hbuniversalcfremote_77665544_fan",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "King Of Fans,  Inc.",
        SIG_MODEL: "HBUniversalCFRemote",
        SIG_NODE_DESC: b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CeilingFan",
    },
    {
        DEV_SIG_DEV_NO: 35,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2048,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4096, 64769],
                SIG_EP_OUTPUT: [3, 4, 6, 8, 25, 768, 4096],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.lds_zbt_cctswitch_d0001_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lds_zbt_cctswitch_d0001_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0019", "1:0x0300"],
        SIG_MANUFACTURER: "LDS",
        SIG_MODEL: "ZBT-CCTSwitch-D0001",
        SIG_NODE_DESC: b"\x02@\x80h\x11RR\x00\x00,R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CCTSwitch",
    },
    {
        DEV_SIG_DEV_NO: 36,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["light.ledvance_a19_rgbw_77665544_level_light_color_on_off"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_a19_rgbw_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "A19 RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 37,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.ledvance_flex_rgbw_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_flex_rgbw_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "FLEX RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 38,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 81,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2821, 64513, 64520],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["switch.ledvance_plug_77665544_on_off"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.ledvance_plug_77665544_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "PLUG",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 39,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["light.ledvance_rt_rgbw_77665544_level_light_color_on_off"],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.ledvance_rt_rgbw_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LEDVANCE",
        SIG_MODEL: "RT RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 40,
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
        DEV_SIG_ENTITIES: [
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input",
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input_2",
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement",
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_apparent_power",
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_rms_current",
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_rms_voltage",
            "switch.lumi_lumi_plug_maus01_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-2-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_analog_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_analog_input_2",
            },
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.lumi_lumi_plug_maus01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement_rms_voltage",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-100-15"): {
                DEV_SIG_CHANNELS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_plug_maus01_77665544_binary_input",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.plug.maus01",
        SIG_NODE_DESC: b"\x01@\x8e_\x11\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Plug",
    },
    {
        DEV_SIG_DEV_NO: 41,
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
        DEV_SIG_ENTITIES: [
            "light.lumi_lumi_relay_c2acn01_77665544_on_off",
            "light.lumi_lumi_relay_c2acn01_77665544_on_off_2",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_apparent_power",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_rms_current",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_rms_voltage",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_relay_c2acn01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement_rms_voltage",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_relay_c2acn01_77665544_on_off_2",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.relay.c2acn01",
        SIG_NODE_DESC: b"\x01@\x8e7\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Relay",
    },
    {
        DEV_SIG_DEV_NO: 42,
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
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_remote_b186acn01_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b186acn01_77665544_power",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b186acn01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "RemoteB186ACN01",
    },
    {
        DEV_SIG_DEV_NO: 43,
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
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_remote_b286acn01_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_remote_b286acn01_77665544_power",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b286acn01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "RemoteB286ACN01",
    },
    {
        DEV_SIG_DEV_NO: 44,
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
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0300"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b286opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 45,
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
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b486opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 46,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 261,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [3, 6, 8, 768],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0300"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b686opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 47,
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
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.remote.b686opcn01",
        SIG_NODE_DESC: b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 48,
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["8:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 49,
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6, 11, 17],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["8:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 50,
        SIG_ENDPOINTS: {
            8: {
                SIG_EP_TYPE: 256,
                DEV_SIG_EP_ID: 8,
                SIG_EP_INPUT: [0, 6, 17],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                DEV_SIG_CHANNELS: ["on_off", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.lumi_lumi_router_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["8:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.router",
        SIG_NODE_DESC: b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 51,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 262,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1024],
                SIG_EP_OUTPUT: [3],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sen_ill_mgl01_77665544_illuminance"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CHANNELS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sen_ill_mgl01_77665544_illuminance",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sen_ill.mgl01",
        SIG_NODE_DESC: b"\x02@\x84n\x12\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 52,
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
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sensor_86sw1_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_86sw1_77665544_power",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_86sw1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "RemoteB186ACN01",
    },
    {
        DEV_SIG_DEV_NO: 53,
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
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sensor_cube_aqgl01_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_power",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_cube.aqgl01",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CubeAQGL01",
    },
    {
        DEV_SIG_DEV_NO: 54,
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
        DEV_SIG_ENTITIES: [
            "sensor.lumi_lumi_sensor_ht_77665544_humidity",
            "sensor.lumi_lumi_sensor_ht_77665544_power",
            "sensor.lumi_lumi_sensor_ht_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                DEV_SIG_CHANNELS: ["humidity"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_ht_77665544_humidity",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_ht",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Weather",
    },
    {
        DEV_SIG_DEV_NO: 55,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2128,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 25, 65535],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_sensor_magnet_77665544_on_off",
            "sensor.lumi_lumi_sensor_magnet_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_magnet_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_magnet",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Magnet",
    },
    {
        DEV_SIG_DEV_NO: 56,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 65535],
                SIG_EP_OUTPUT: [0, 4, 6, 65535],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_sensor_magnet_aq2_77665544_on_off",
            "sensor.lumi_lumi_sensor_magnet_aq2_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_magnet_aq2_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Opening",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_magnet_aq2_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_magnet.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MagnetAQ2",
    },
    {
        DEV_SIG_DEV_NO: 57,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 263,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1024, 1030, 1280, 65535],
                SIG_EP_OUTPUT: [0, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_ias_zone",
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_occupancy",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_illuminance",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CHANNELS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_motion_aq2_77665544_illuminance",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1030"): {
                DEV_SIG_CHANNELS: ["occupancy"],
                DEV_SIG_ENT_MAP_CLASS: "Occupancy",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_occupancy",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_motion.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MotionAQ2",
    },
    {
        DEV_SIG_DEV_NO: 58,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 12, 18, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_sensor_smoke_77665544_ias_zone",
            "sensor.lumi_lumi_sensor_smoke_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_smoke_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_smoke_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_smoke",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MijiaHoneywellSmokeDetectorSensor",
    },
    {
        DEV_SIG_DEV_NO: 59,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3],
                SIG_EP_OUTPUT: [0, 4, 5, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sensor_switch_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MijaButton",
    },
    {
        DEV_SIG_DEV_NO: 60,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 65535],
                SIG_EP_OUTPUT: [0, 4, 6, 65535],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sensor_switch_aq2_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq2_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch.aq2",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SwitchAQ2",
    },
    {
        DEV_SIG_DEV_NO: 61,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 6,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 18],
                SIG_EP_OUTPUT: [0, 6],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.lumi_lumi_sensor_switch_aq3_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_switch_aq3_77665544_power",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_switch.aq3",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SwitchAQ3",
    },
    {
        DEV_SIG_DEV_NO: 62,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1280],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_sensor_wleak_aq1_77665544_ias_zone",
            "sensor.lumi_lumi_sensor_wleak_aq1_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_sensor_wleak_aq1_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_sensor_wleak_aq1_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.sensor_wleak.aq1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "LeakAQ1",
    },
    {
        DEV_SIG_DEV_NO: 63,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 10,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 25, 257, 1280],
                SIG_EP_OUTPUT: [0, 3, 4, 5, 25],
                SIG_EP_PROFILE: 260,
            },
            2: {
                SIG_EP_TYPE: 24322,
                DEV_SIG_EP_ID: 2,
                SIG_EP_INPUT: [3],
                SIG_EP_OUTPUT: [3, 4, 5, 18],
                SIG_EP_PROFILE: 260,
            },
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.lumi_lumi_vibration_aq1_77665544_ias_zone",
            "lock.lumi_lumi_vibration_aq1_77665544_door_lock",
            "sensor.lumi_lumi_vibration_aq1_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_vibration_aq1_77665544_power",
            },
            ("lock", "00:11:22:33:44:55:66:77-1-257"): {
                DEV_SIG_CHANNELS: ["door_lock"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaDoorLock",
                DEV_SIG_ENT_MAP_ID: "lock.lumi_lumi_vibration_aq1_77665544_door_lock",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.lumi_lumi_vibration_aq1_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0019", "2:0x0005"],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.vibration.aq1",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "VibrationAQ1",
    },
    {
        DEV_SIG_DEV_NO: 64,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 24321,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 1026, 1027, 1029, 65535],
                SIG_EP_OUTPUT: [0, 4, 65535],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.lumi_lumi_weather_77665544_humidity",
            "sensor.lumi_lumi_weather_77665544_power",
            "sensor.lumi_lumi_weather_77665544_pressure",
            "sensor.lumi_lumi_weather_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                DEV_SIG_CHANNELS: ["pressure"],
                DEV_SIG_ENT_MAP_CLASS: "Pressure",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_77665544_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                DEV_SIG_CHANNELS: ["humidity"],
                DEV_SIG_ENT_MAP_CLASS: "Humidity",
                DEV_SIG_ENT_MAP_ID: "sensor.lumi_lumi_weather_77665544_humidity",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "LUMI",
        SIG_MODEL: "lumi.weather",
        SIG_NODE_DESC: b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Weather",
    },
    {
        DEV_SIG_DEV_NO: 65,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1280],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.nyce_3010_77665544_ias_zone",
            "sensor.nyce_3010_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3010_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.nyce_3010_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "NYCE",
        SIG_MODEL: "3010",
        SIG_NODE_DESC: b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 66,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1280],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.nyce_3014_77665544_ias_zone",
            "sensor.nyce_3014_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.nyce_3014_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.nyce_3014_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "NYCE",
        SIG_MODEL: "3014",
        SIG_NODE_DESC: b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 67,
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
        DEV_SIG_ENTITIES: ["1:0x0019"],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: None,
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x10@\x0f5\x11Y=\x00@\x00=\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 68,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 48879,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [1280],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [],
        DEV_SIG_ENT_MAP: {},
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: None,
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x00@\x8f\xcd\xabR\x80\x00\x00\x00\x80\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 69,
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.osram_lightify_a19_rgbw_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_a19_rgbw_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["3:0x0019"],
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY A19 RGBW",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        DEV_SIG_ZHA_QUIRK: "LIGHTIFYA19RGBW",
    },
    {
        DEV_SIG_DEV_NO: 70,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 2821],
                SIG_EP_OUTPUT: [3, 6, 8, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["sensor.osram_lightify_dimming_switch_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_dimming_switch_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0006", "1:0x0008", "1:0x0019"],
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY Dimming Switch",
        SIG_NODE_DESC: b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "CentraLite3130",
    },
    {
        DEV_SIG_DEV_NO: 71,
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.osram_lightify_flex_rgbw_77665544_level_light_color_on_off"
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_flex_rgbw_77665544_level_light_color_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: ["3:0x0019"],
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY Flex RGBW",
        SIG_NODE_DESC: b"\x19@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        DEV_SIG_ZHA_QUIRK: "FlexRGBW",
    },
    {
        DEV_SIG_DEV_NO: 72,
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 258,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2820, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.osram_lightify_rt_tunable_white_77665544_level_light_color_on_off",
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement",
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_apparent_power",
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_rms_current",
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_rms_voltage",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.osram_lightify_rt_tunable_white_77665544_level_light_color_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["3:0x0019"],
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "LIGHTIFY RT Tunable White",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        DEV_SIG_ZHA_QUIRK: "A19TunableWhite",
    },
    {
        DEV_SIG_DEV_NO: 73,
        SIG_ENDPOINTS: {
            3: {
                SIG_EP_TYPE: 16,
                DEV_SIG_EP_ID: 3,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2820, 4096, 64527],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 49246,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.osram_plug_01_77665544_electrical_measurement",
            "sensor.osram_plug_01_77665544_electrical_measurement_apparent_power",
            "sensor.osram_plug_01_77665544_electrical_measurement_rms_current",
            "sensor.osram_plug_01_77665544_electrical_measurement_rms_voltage",
            "switch.osram_plug_01_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.osram_plug_01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_plug_01_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["3:0x0019"],
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "Plug 01",
        SIG_NODE_DESC: b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
    },
    {
        DEV_SIG_DEV_NO: 74,
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
        DEV_SIG_ENTITIES: ["sensor.osram_switch_4x_lightify_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.osram_switch_4x_lightify_77665544_power",
            }
        },
        DEV_SIG_EVT_CHANNELS: [
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
        SIG_MANUFACTURER: "OSRAM",
        SIG_MODEL: "Switch 4x-LIGHTIFY",
        SIG_NODE_DESC: b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "LightifyX4",
    },
    {
        DEV_SIG_DEV_NO: 75,
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
        DEV_SIG_ENTITIES: ["sensor.philips_rwl020_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-2-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.philips_rwl020_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-2-15"): {
                DEV_SIG_CHANNELS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.philips_rwl020_77665544_binary_input",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0006", "1:0x0008", "2:0x0019"],
        SIG_MANUFACTURER: "Philips",
        SIG_MODEL: "RWL020",
        SIG_NODE_DESC: b"\x02@\x80\x0b\x10G-\x00\x00\x00-\x00\x00",
        DEV_SIG_ZHA_QUIRK: "PhilipsRWL021",
    },
    {
        DEV_SIG_DEV_NO: 76,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.samjin_button_77665544_ias_zone",
            "sensor.samjin_button_77665544_power",
            "sensor.samjin_button_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_button_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_button_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "button",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SamjinButton",
    },
    {
        DEV_SIG_DEV_NO: 77,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 64514],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.samjin_multi_77665544_ias_zone",
            "binary_sensor.samjin_multi_77665544_manufacturer_specific",
            "sensor.samjin_multi_77665544_power",
            "sensor.samjin_multi_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_multi_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_multi_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "multi",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SmartthingsMultiPurposeSensor",
    },
    {
        DEV_SIG_DEV_NO: 78,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.samjin_water_77665544_ias_zone",
            "sensor.samjin_water_77665544_power",
            "sensor.samjin_water_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.samjin_water_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.samjin_water_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Samjin",
        SIG_MODEL: "water",
        SIG_NODE_DESC: b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 79,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 0,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 2820, 2821],
                SIG_EP_OUTPUT: [0, 1, 3, 4, 5, 6, 25, 2820, 2821],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement",
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_apparent_power",
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_rms_current",
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_rms_voltage",
            "switch.securifi_ltd_unk_model_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.securifi_ltd_unk_model_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.securifi_ltd_unk_model_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0005", "1:0x0006", "1:0x0019"],
        SIG_MANUFACTURER: "Securifi Ltd.",
        SIG_MODEL: None,
        SIG_NODE_DESC: b"\x01@\x8e\x02\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 80,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.sercomm_corp_sz_dws04n_sf_77665544_ias_zone",
            "sensor.sercomm_corp_sz_dws04n_sf_77665544_power",
            "sensor.sercomm_corp_sz_dws04n_sf_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_dws04n_sf_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.sercomm_corp_sz_dws04n_sf_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-DWS04N_SF",
        SIG_NODE_DESC: b"\x02@\x801\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 81,
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
        DEV_SIG_ENTITIES: [
            "light.sercomm_corp_sz_esw01_77665544_on_off",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_apparent_power",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_rms_current",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_rms_voltage",
            "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering",
            "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.sercomm_corp_sz_esw01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering_summation_delivered",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019", "2:0x0006"],
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-ESW01",
        SIG_NODE_DESC: b"\x01@\x8e1\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 82,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1024, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.sercomm_corp_sz_pir04_77665544_ias_zone",
            "sensor.sercomm_corp_sz_pir04_77665544_illuminance",
            "sensor.sercomm_corp_sz_pir04_77665544_power",
            "sensor.sercomm_corp_sz_pir04_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                DEV_SIG_CHANNELS: ["illuminance"],
                DEV_SIG_ENT_MAP_CLASS: "Illuminance",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_77665544_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sercomm_corp_sz_pir04_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.sercomm_corp_sz_pir04_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Sercomm Corp.",
        SIG_MODEL: "SZ-PIR04",
        SIG_NODE_DESC: b"\x02@\x801\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 83,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 2820, 2821, 65281],
                SIG_EP_OUTPUT: [3, 4, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement",
            "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_apparent_power",
            "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_rms_current",
            "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_rms_voltage",
            "switch.sinope_technologies_rm3250zb_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.sinope_technologies_rm3250zb_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "RM3250ZB",
        SIG_NODE_DESC: b"\x11@\x8e\x9c\x11G+\x00\x00*+\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 84,
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
        DEV_SIG_ENTITIES: [
            "climate.sinope_technologies_th1123zb_77665544_thermostat",
            "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement",
            "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_apparent_power",
            "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_rms_current",
            "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_rms_voltage",
            "sensor.sinope_technologies_th1123zb_77665544_temperature",
            "sensor.sinope_technologies_th1123zb_77665544_thermostat_hvac_action",
        ],
        DEV_SIG_ENT_MAP: {
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "Thermostat",
                DEV_SIG_ENT_MAP_ID: "climate.sinope_technologies_th1123zb_77665544_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement_rms_voltage",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CHANNELS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "ThermostatHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1123zb_77665544_thermostat_hvac_action",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "TH1123ZB",
        SIG_NODE_DESC: b"\x12@\x8c\x9c\x11G+\x00\x00\x00+\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SinopeTechnologiesThermostat",
    },
    {
        DEV_SIG_DEV_NO: 85,
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
        DEV_SIG_ENTITIES: [
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement",
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_apparent_power",
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_rms_current",
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_rms_voltage",
            "sensor.sinope_technologies_th1124zb_77665544_temperature",
            "sensor.sinope_technologies_th1124zb_77665544_thermostat_hvac_action",
            "climate.sinope_technologies_th1124zb_77665544_thermostat",
        ],
        DEV_SIG_ENT_MAP: {
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "Thermostat",
                DEV_SIG_ENT_MAP_ID: "climate.sinope_technologies_th1124zb_77665544_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CHANNELS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "ThermostatHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_thermostat_hvac_action",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement_rms_voltage",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Sinope Technologies",
        SIG_MODEL: "TH1124ZB",
        SIG_NODE_DESC: b"\x11@\x8e\x9c\x11G+\x00\x00\x00+\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SinopeTechnologiesThermostat",
    },
    {
        DEV_SIG_DEV_NO: 86,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 9, 15, 2820],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.smartthings_outletv4_77665544_electrical_measurement",
            "sensor.smartthings_outletv4_77665544_electrical_measurement_apparent_power",
            "sensor.smartthings_outletv4_77665544_electrical_measurement_rms_current",
            "sensor.smartthings_outletv4_77665544_electrical_measurement_rms_voltage",
            "switch.smartthings_outletv4_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.smartthings_outletv4_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurement",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-apparent_power"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementApparentPower",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_77665544_electrical_measurement_apparent_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_current"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSCurrent",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_77665544_electrical_measurement_rms_current",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820-rms_voltage"): {
                DEV_SIG_CHANNELS: ["electrical_measurement"],
                DEV_SIG_ENT_MAP_CLASS: "ElectricalMeasurementRMSVoltage",
                DEV_SIG_ENT_MAP_ID: "sensor.smartthings_outletv4_77665544_electrical_measurement_rms_voltage",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-15"): {
                DEV_SIG_CHANNELS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.smartthings_outletv4_77665544_binary_input",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "SmartThings",
        SIG_MODEL: "outletv4",
        SIG_NODE_DESC: b"\x01@\x8e\n\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 87,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 32768,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 15, 32],
                SIG_EP_OUTPUT: [3, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["device_tracker.smartthings_tagv4_77665544_power"],
        DEV_SIG_ENT_MAP: {
            ("device_tracker", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "ZHADeviceScannerEntity",
                DEV_SIG_ENT_MAP_ID: "device_tracker.smartthings_tagv4_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-15"): {
                DEV_SIG_CHANNELS: ["binary_input"],
                DEV_SIG_ENT_MAP_CLASS: "BinaryInput",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.smartthings_tagv4_77665544_binary_input",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "SmartThings",
        SIG_MODEL: "tagv4",
        SIG_NODE_DESC: b"\x02@\x80\n\x11RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "SmartThingsTagV4",
    },
    {
        DEV_SIG_DEV_NO: 88,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 25],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: ["switch.third_reality_inc_3rss007z_77665544_on_off"],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.third_reality_inc_3rss007z_77665544_on_off",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "Third Reality, Inc",
        SIG_MODEL: "3RSS007Z",
        SIG_NODE_DESC: b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 89,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 2,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 6, 25],
                SIG_EP_OUTPUT: [1],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.third_reality_inc_3rss008z_77665544_power",
            "switch.third_reality_inc_3rss008z_77665544_on_off",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.third_reality_inc_3rss008z_77665544_power",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.third_reality_inc_3rss008z_77665544_on_off",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "Third Reality, Inc",
        SIG_MODEL: "3RSS008Z",
        SIG_NODE_DESC: b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Switch",
    },
    {
        DEV_SIG_DEV_NO: 90,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 32, 1026, 1280, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.visonic_mct_340_e_77665544_ias_zone",
            "sensor.visonic_mct_340_e_77665544_power",
            "sensor.visonic_mct_340_e_77665544_temperature",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.visonic_mct_340_e_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.visonic_mct_340_e_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Visonic",
        SIG_MODEL: "MCT-340 E",
        SIG_NODE_DESC: b"\x02@\x80\x11\x10RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "MCT340E",
    },
    {
        DEV_SIG_DEV_NO: 91,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 769,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 4, 5, 32, 513, 514, 516, 2821],
                SIG_EP_OUTPUT: [10, 25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "climate.zen_within_zen_01_77665544_fan_thermostat",
            "sensor.zen_within_zen_01_77665544_thermostat_hvac_action",
            "sensor.zen_within_zen_01_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_77665544_power",
            },
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["thermostat", "fan"],
                DEV_SIG_ENT_MAP_CLASS: "ZenWithinThermostat",
                DEV_SIG_ENT_MAP_ID: "climate.zen_within_zen_01_77665544_fan_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-513-hvac_action"): {
                DEV_SIG_CHANNELS: ["thermostat"],
                DEV_SIG_ENT_MAP_CLASS: "ZenHVACAction",
                DEV_SIG_ENT_MAP_ID: "sensor.zen_within_zen_01_77665544_thermostat_hvac_action",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "Zen Within",
        SIG_MODEL: "Zen-01",
        SIG_NODE_DESC: b"\x02@\x80X\x11R\x80\x00\x00\x00\x80\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 92,
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
        DEV_SIG_ENTITIES: [
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_2",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_3",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_4",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_4",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_3",
            },
            ("light", "00:11:22:33:44:55:66:77-3"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-4"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_2",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "_TYZB01_ns1ndbww",
        SIG_MODEL: "TS0004",
        SIG_NODE_DESC: b"\x01@\x8e\x02\x10R\x00\x02\x00,\x00\x02\x00",
    },
    {
        DEV_SIG_DEV_NO: 93,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 1026,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 1, 3, 21, 32, 1280, 2821],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "binary_sensor.netvox_z308e3ed_77665544_ias_zone",
            "sensor.netvox_z308e3ed_77665544_power",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.netvox_z308e3ed_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                DEV_SIG_CHANNELS: ["ias_zone"],
                DEV_SIG_ENT_MAP_CLASS: "IASZone",
                DEV_SIG_ENT_MAP_ID: "binary_sensor.netvox_z308e3ed_77665544_ias_zone",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "netvox",
        SIG_MODEL: "Z308E3ED",
        SIG_NODE_DESC: b"\x02@\x80\x9f\x10RR\x00\x00\x00R\x00\x00",
        DEV_SIG_ZHA_QUIRK: "Z308E3ED",
    },
    {
        DEV_SIG_DEV_NO: 94,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.sengled_e11_g13_77665544_level_on_off",
            "sensor.sengled_e11_g13_77665544_smartenergy_metering",
            "sensor.sengled_e11_g13_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.sengled_e11_g13_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e11_g13_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "E11-G13",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 95,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.sengled_e12_n14_77665544_level_on_off",
            "sensor.sengled_e12_n14_77665544_smartenergy_metering",
            "sensor.sengled_e12_n14_77665544_smartenergy_metering_sumaiton_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.sengled_e12_n14_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_e12_n14_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "E12-N14",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 96,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 257,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 1794, 2821],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "light.sengled_z01_a19nae26_77665544_level_light_color_on_off",
            "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering",
            "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering_summation_delivered",
        ],
        DEV_SIG_ENT_MAP: {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "light_color", "on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Light",
                DEV_SIG_ENT_MAP_ID: "light.sengled_z01_a19nae26_77665544_level_light_color_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergyMetering",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794-summation_delivered"): {
                DEV_SIG_CHANNELS: ["smartenergy_metering"],
                DEV_SIG_ENT_MAP_CLASS: "SmartEnergySummation",
                DEV_SIG_ENT_MAP_ID: "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering_summation_delivered",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["1:0x0019"],
        SIG_MANUFACTURER: "sengled",
        SIG_MODEL: "Z01-A19NAE26",
        SIG_NODE_DESC: b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 97,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 512,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 10, 21, 256, 64544, 64545],
                SIG_EP_OUTPUT: [3, 64544],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "cover.unk_manufacturer_unk_model_77665544_level_on_off_shade"
        ],
        DEV_SIG_ENT_MAP: {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                DEV_SIG_CHANNELS: ["level", "on_off", "shade"],
                DEV_SIG_ENT_MAP_CLASS: "Shade",
                DEV_SIG_ENT_MAP_ID: "cover.unk_manufacturer_unk_model_77665544_level_on_off_shade",
            }
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "unk_manufacturer",
        SIG_MODEL: "unk_model",
        SIG_NODE_DESC: b"\x01@\x8e\x10\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 98,
        SIG_ENDPOINTS: {
            208: {
                DEV_SIG_EP_ID: 208,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000C],
                SIG_EP_OUTPUT: [],
            },
            209: {
                DEV_SIG_EP_ID: 209,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000C],
                SIG_EP_OUTPUT: [],
            },
            210: {
                DEV_SIG_EP_ID: 210,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000C],
                SIG_EP_OUTPUT: [],
            },
            211: {
                DEV_SIG_EP_ID: 211,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000C],
                SIG_EP_OUTPUT: [],
            },
            212: {
                DEV_SIG_EP_ID: 212,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            213: {
                DEV_SIG_EP_ID: 213,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            214: {
                DEV_SIG_EP_ID: 214,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            215: {
                DEV_SIG_EP_ID: 215,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000C],
                SIG_EP_OUTPUT: [],
            },
            216: {
                DEV_SIG_EP_ID: 216,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            217: {
                DEV_SIG_EP_ID: 217,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            218: {
                DEV_SIG_EP_ID: 218,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000D],
                SIG_EP_OUTPUT: [],
            },
            219: {
                DEV_SIG_EP_ID: 219,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006, 0x000D],
                SIG_EP_OUTPUT: [],
            },
            220: {
                DEV_SIG_EP_ID: 220,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            221: {
                DEV_SIG_EP_ID: 221,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            222: {
                DEV_SIG_EP_ID: 222,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0006],
                SIG_EP_OUTPUT: [],
            },
            232: {
                DEV_SIG_EP_ID: 232,
                SIG_EP_PROFILE: 49413,
                SIG_EP_TYPE: 0x0001,
                SIG_EP_INPUT: [0x0011, 0x0092],
                SIG_EP_OUTPUT: [0x0008, 0x0011],
            },
        },
        DEV_SIG_ENTITIES: [
            "switch.digi_xbee3_77665544_on_off",
            "switch.digi_xbee3_77665544_on_off_2",
            "switch.digi_xbee3_77665544_on_off_3",
            "switch.digi_xbee3_77665544_on_off_4",
            "switch.digi_xbee3_77665544_on_off_5",
            "switch.digi_xbee3_77665544_on_off_6",
            "switch.digi_xbee3_77665544_on_off_7",
            "switch.digi_xbee3_77665544_on_off_8",
            "switch.digi_xbee3_77665544_on_off_9",
            "switch.digi_xbee3_77665544_on_off_10",
            "switch.digi_xbee3_77665544_on_off_11",
            "switch.digi_xbee3_77665544_on_off_12",
            "switch.digi_xbee3_77665544_on_off_13",
            "switch.digi_xbee3_77665544_on_off_14",
            "switch.digi_xbee3_77665544_on_off_15",
            "sensor.digi_xbee3_77665544_analog_input",
            "sensor.digi_xbee3_77665544_analog_input_2",
            "sensor.digi_xbee3_77665544_analog_input_3",
            "sensor.digi_xbee3_77665544_analog_input_4",
            "number.digi_xbee3_77665544_analog_output",
            "number.digi_xbee3_77665544_analog_output_2",
        ],
        DEV_SIG_ENT_MAP: {
            ("switch", "00:11:22:33:44:55:66:77-208-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off",
            },
            ("switch", "00:11:22:33:44:55:66:77-209-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_2",
            },
            ("switch", "00:11:22:33:44:55:66:77-210-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_3",
            },
            ("switch", "00:11:22:33:44:55:66:77-211-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_4",
            },
            ("switch", "00:11:22:33:44:55:66:77-212-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_5",
            },
            ("switch", "00:11:22:33:44:55:66:77-213-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_6",
            },
            ("switch", "00:11:22:33:44:55:66:77-214-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_7",
            },
            ("switch", "00:11:22:33:44:55:66:77-215-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_8",
            },
            ("switch", "00:11:22:33:44:55:66:77-216-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_9",
            },
            ("switch", "00:11:22:33:44:55:66:77-217-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_10",
            },
            ("switch", "00:11:22:33:44:55:66:77-218-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_11",
            },
            ("switch", "00:11:22:33:44:55:66:77-219-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_12",
            },
            ("switch", "00:11:22:33:44:55:66:77-220-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_13",
            },
            ("switch", "00:11:22:33:44:55:66:77-221-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_14",
            },
            ("switch", "00:11:22:33:44:55:66:77-222-6"): {
                DEV_SIG_CHANNELS: ["on_off"],
                DEV_SIG_ENT_MAP_CLASS: "Switch",
                DEV_SIG_ENT_MAP_ID: "switch.digi_xbee3_77665544_on_off_15",
            },
            ("sensor", "00:11:22:33:44:55:66:77-208-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_77665544_analog_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-209-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_77665544_analog_input_2",
            },
            ("sensor", "00:11:22:33:44:55:66:77-210-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_77665544_analog_input_3",
            },
            ("sensor", "00:11:22:33:44:55:66:77-211-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_77665544_analog_input_4",
            },
            ("sensor", "00:11:22:33:44:55:66:77-215-12"): {
                DEV_SIG_CHANNELS: ["analog_input"],
                DEV_SIG_ENT_MAP_CLASS: "AnalogInput",
                DEV_SIG_ENT_MAP_ID: "sensor.digi_xbee3_77665544_analog_input_5",
            },
            ("number", "00:11:22:33:44:55:66:77-218-13"): {
                DEV_SIG_CHANNELS: ["analog_output"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaNumber",
                DEV_SIG_ENT_MAP_ID: "number.digi_xbee3_77665544_analog_output",
            },
            ("number", "00:11:22:33:44:55:66:77-219-13"): {
                DEV_SIG_CHANNELS: ["analog_output"],
                DEV_SIG_ENT_MAP_CLASS: "ZhaNumber",
                DEV_SIG_ENT_MAP_ID: "number.digi_xbee3_77665544_analog_output_2",
            },
        },
        DEV_SIG_EVT_CHANNELS: ["232:0x0008"],
        SIG_MANUFACTURER: "Digi",
        SIG_MODEL: "XBee3",
        SIG_NODE_DESC: b"\x01@\x8e\x1e\x10R\xff\x00\x00,\xff\x00\x00",
    },
    {
        DEV_SIG_DEV_NO: 99,
        SIG_ENDPOINTS: {
            1: {
                SIG_EP_TYPE: 0x000C,
                DEV_SIG_EP_ID: 1,
                SIG_EP_INPUT: [0x0000, 0x0001, 0x0402, 0x0408],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: 260,
            }
        },
        DEV_SIG_ENTITIES: [
            "sensor.efektalab_ru_efekta_pws_77665544_power",
            "sensor.efektalab_ru_efekta_pws_77665544_temperature",
            "sensor.efektalab_ru_efekta_pws_77665544_soil_moisture",
        ],
        DEV_SIG_ENT_MAP: {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                DEV_SIG_CHANNELS: ["power"],
                DEV_SIG_ENT_MAP_CLASS: "Battery",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                DEV_SIG_CHANNELS: ["temperature"],
                DEV_SIG_ENT_MAP_CLASS: "Temperature",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1032"): {
                DEV_SIG_CHANNELS: ["soil_moisture"],
                DEV_SIG_ENT_MAP_CLASS: "SoilMoisture",
                DEV_SIG_ENT_MAP_ID: "sensor.efektalab_ru_efekta_pws_77665544_soil_moisture",
            },
        },
        DEV_SIG_EVT_CHANNELS: [],
        SIG_MANUFACTURER: "efektalab.ru",
        SIG_MODEL: "EFEKTA_PWS",
        SIG_NODE_DESC: b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
]
