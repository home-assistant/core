"""Example Zigbee Devices."""

DEVICES = [
    {
        "device_no": 0,
        "endpoints": {
            1: {
                "device_type": 2080,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4096, 64716],
                "out_clusters": [3, 4, 6, 8, 4096, 64716],
                "profile_id": 260,
            }
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0006", "1:0x0008"],
        "manufacturer": "ADUROLIGHT",
        "model": "Adurolight_NCC",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        "zha_quirks": "AdurolightNCC",
    },
    {
        "device_no": 1,
        "endpoints": {
            5: {
                "device_type": 1026,
                "endpoint_id": 5,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.bosch_isw_zpr1_wp13_77665544_ias_zone",
            "sensor.bosch_isw_zpr1_wp13_77665544_power",
            "sensor.bosch_isw_zpr1_wp13_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-5-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.bosch_isw_zpr1_wp13_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-5-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.bosch_isw_zpr1_wp13_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-5-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.bosch_isw_zpr1_wp13_77665544_ias_zone",
            },
        },
        "event_channels": ["5:0x0019"],
        "manufacturer": "Bosch",
        "model": "ISW-ZPR1-WP13",
        "node_descriptor": b"\x02@\x08\x00\x00l\x00\x00\x00\x00\x00\x00\x00",
    },
    {
        "device_no": 2,
        "endpoints": {
            1: {
                "device_type": 1,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 2821],
                "out_clusters": [3, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.centralite_3130_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_3130_77665544_power",
            }
        },
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3130",
        "node_descriptor": b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLite3130",
    },
    {
        "device_no": 3,
        "endpoints": {
            1: {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794, 2820, 2821, 64515],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.centralite_3210_l_77665544_electrical_measurement",
            "sensor.centralite_3210_l_77665544_smartenergy_metering",
            "switch.centralite_3210_l_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.centralite_3210_l_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.centralite_3210_l_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.centralite_3210_l_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3210-L",
        "node_descriptor": b"\x01@\x8eN\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 4,
        "endpoints": {
            1: {
                "device_type": 770,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 2821, 64581],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.centralite_3310_s_77665544_manufacturer_specific",
            "sensor.centralite_3310_s_77665544_power",
            "sensor.centralite_3310_s_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_3310_s_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.centralite_3310_s_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-64581"): {
                "channels": ["manufacturer_specific"],
                "entity_class": "Humidity",
                "entity_id": "sensor.centralite_3310_s_77665544_manufacturer_specific",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3310-S",
        "node_descriptor": b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLite3310S",
    },
    {
        "device_no": 5,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            2: {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64527],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3315_s_77665544_ias_zone",
            "sensor.centralite_3315_s_77665544_power",
            "sensor.centralite_3315_s_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_3315_s_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.centralite_3315_s_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.centralite_3315_s_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3315-S",
        "node_descriptor": b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLiteIASSensor",
    },
    {
        "device_no": 6,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            2: {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64527],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3320_l_77665544_ias_zone",
            "sensor.centralite_3320_l_77665544_power",
            "sensor.centralite_3320_l_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_3320_l_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.centralite_3320_l_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.centralite_3320_l_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3320-L",
        "node_descriptor": b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLiteIASSensor",
    },
    {
        "device_no": 7,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            2: {
                "device_type": 263,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64582],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3326_l_77665544_ias_zone",
            "sensor.centralite_3326_l_77665544_power",
            "sensor.centralite_3326_l_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_3326_l_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.centralite_3326_l_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.centralite_3326_l_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "3326-L",
        "node_descriptor": b"\x02@\x80\xdf\xc2RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLiteMotionSensor",
    },
    {
        "device_no": 8,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            2: {
                "device_type": 263,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 1030, 2821],
                "out_clusters": [3],
                "profile_id": 260,
            },
        },
        "entities": [
            "binary_sensor.centralite_motion_sensor_a_77665544_ias_zone",
            "binary_sensor.centralite_motion_sensor_a_77665544_occupancy",
            "sensor.centralite_motion_sensor_a_77665544_power",
            "sensor.centralite_motion_sensor_a_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.centralite_motion_sensor_a_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.centralite_motion_sensor_a_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.centralite_motion_sensor_a_77665544_ias_zone",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-2-1030"): {
                "channels": ["occupancy"],
                "entity_class": "Occupancy",
                "entity_id": "binary_sensor.centralite_motion_sensor_a_77665544_occupancy",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "CentraLite",
        "model": "Motion Sensor-A",
        "node_descriptor": b"\x02@\x80N\x10RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLite3305S",
    },
    {
        "device_no": 9,
        "endpoints": {
            1: {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794],
                "out_clusters": [0],
                "profile_id": 260,
            },
            4: {
                "device_type": 9,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [25],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering",
            "switch.climaxtechnology_psmp5_00_00_02_02tc_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.climaxtechnology_psmp5_00_00_02_02tc_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.climaxtechnology_psmp5_00_00_02_02tc_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["4:0x0019"],
        "manufacturer": "ClimaxTechnology",
        "model": "PSMP5_00.00.02.02TC",
        "node_descriptor": b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 10,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 1280, 1282],
                "out_clusters": [0],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.climaxtechnology_sd8sc_00_00_03_12tc_77665544_ias_zone"
        ],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.climaxtechnology_sd8sc_00_00_03_12tc_77665544_ias_zone",
            }
        },
        "event_channels": [],
        "manufacturer": "ClimaxTechnology",
        "model": "SD8SC_00.00.03.12TC",
        "node_descriptor": b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 11,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 1280],
                "out_clusters": [0],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.climaxtechnology_ws15_00_00_03_03tc_77665544_ias_zone"
        ],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.climaxtechnology_ws15_00_00_03_03tc_77665544_ias_zone",
            }
        },
        "event_channels": [],
        "manufacturer": "ClimaxTechnology",
        "model": "WS15_00.00.03.03TC",
        "node_descriptor": b"\x02@\x80\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 12,
        "endpoints": {
            11: {
                "device_type": 528,
                "endpoint_id": 11,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768],
                "out_clusters": [],
                "profile_id": 49246,
            },
            13: {
                "device_type": 57694,
                "endpoint_id": 13,
                "in_clusters": [4096],
                "out_clusters": [4096],
                "profile_id": 49246,
            },
        },
        "entities": [
            "light.feibit_inc_co_fb56_zcw08ku1_1_77665544_level_light_color_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-11"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.feibit_inc_co_fb56_zcw08ku1_1_77665544_level_light_color_on_off",
            }
        },
        "event_channels": [],
        "manufacturer": "Feibit Inc co.",
        "model": "FB56-ZCW08KU1.1",
        "node_descriptor": b"\x01@\x8e\x00\x00P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 13,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1280, 1282],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.heiman_smokesensor_em_77665544_ias_zone",
            "sensor.heiman_smokesensor_em_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.heiman_smokesensor_em_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.heiman_smokesensor_em_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "HEIMAN",
        "model": "SmokeSensor-EM",
        "node_descriptor": b"\x02@\x80\x0b\x12RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 14,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 1280],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["binary_sensor.heiman_co_v16_77665544_ias_zone"],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.heiman_co_v16_77665544_ias_zone",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Heiman",
        "model": "CO_V16",
        "node_descriptor": b"\x02@\x84\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
    },
    {
        "device_no": 15,
        "endpoints": {
            1: {
                "device_type": 1027,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 9, 1280, 1282],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": ["binary_sensor.heiman_warningdevice_77665544_ias_zone"],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.heiman_warningdevice_77665544_ias_zone",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Heiman",
        "model": "WarningDevice",
        "node_descriptor": b"\x01@\x8e\x0b\x12RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 16,
        "endpoints": {
            6: {
                "device_type": 1026,
                "endpoint_id": 6,
                "in_clusters": [0, 1, 3, 32, 1024, 1026, 1280],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.hivehome_com_mot003_77665544_ias_zone",
            "sensor.hivehome_com_mot003_77665544_illuminance",
            "sensor.hivehome_com_mot003_77665544_power",
            "sensor.hivehome_com_mot003_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-6-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.hivehome_com_mot003_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1024"): {
                "channels": ["illuminance"],
                "entity_class": "Illuminance",
                "entity_id": "sensor.hivehome_com_mot003_77665544_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-6-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.hivehome_com_mot003_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-6-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.hivehome_com_mot003_77665544_ias_zone",
            },
        },
        "event_channels": ["6:0x0019"],
        "manufacturer": "HiveHome.com",
        "model": "MOT003",
        "node_descriptor": b"\x02@\x809\x10PP\x00\x00\x00P\x00\x00",
        "zha_quirks": "MOT003",
    },
    {
        "device_no": 17,
        "endpoints": {
            1: {
                "device_type": 268,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 4096, 64636],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 260,
            },
            242: {
                "device_type": 97,
                "endpoint_id": 242,
                "in_clusters": [33],
                "out_clusters": [33],
                "profile_id": 41440,
            },
        },
        "entities": [
            "light.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_77665544_level_light_color_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ikea_of_sweden_tradfri_bulb_e12_ws_opal_600lm_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E12 WS opal 600lm",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
    },
    {
        "device_no": 18,
        "endpoints": {
            1: {
                "device_type": 512,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 49246,
            }
        },
        "entities": [
            "light.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_77665544_level_light_color_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ikea_of_sweden_tradfri_bulb_e26_cws_opal_600lm_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 CWS opal 600lm",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 19,
        "endpoints": {
            1: {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 2821, 4096],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 49246,
            }
        },
        "entities": [
            "light.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_77665544_level_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ikea_of_sweden_tradfri_bulb_e26_w_opal_1000lm_77665544_level_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 W opal 1000lm",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 20,
        "endpoints": {
            1: {
                "device_type": 544,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 4096],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 49246,
            }
        },
        "entities": [
            "light.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_77665544_level_light_color_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ikea_of_sweden_tradfri_bulb_e26_ws_opal_980lm_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 WS opal 980lm",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 21,
        "endpoints": {
            1: {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 2821, 4096],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_77665544_level_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ikea_of_sweden_tradfri_bulb_e26_opal_1000lm_77665544_level_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 opal 1000lm",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 22,
        "endpoints": {
            1: {
                "device_type": 266,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 64636],
                "out_clusters": [5, 25, 32],
                "profile_id": 260,
            }
        },
        "entities": ["switch.ikea_of_sweden_tradfri_control_outlet_77665544_on_off"],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.ikea_of_sweden_tradfri_control_outlet_77665544_on_off",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI control outlet",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
        "zha_quirks": "TradfriPlug",
    },
    {
        "device_no": 23,
        "endpoints": {
            1: {
                "device_type": 2128,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 2821, 4096],
                "out_clusters": [3, 4, 6, 25, 4096],
                "profile_id": 49246,
            }
        },
        "entities": [
            "binary_sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_on_off",
            "sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.ikea_of_sweden_tradfri_motion_sensor_77665544_on_off",
            },
        },
        "event_channels": ["1:0x0006", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI motion sensor",
        "node_descriptor": b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "IkeaTradfriMotion",
    },
    {
        "device_no": 24,
        "endpoints": {
            1: {
                "device_type": 2080,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 32, 4096, 64636],
                "out_clusters": [3, 4, 6, 8, 25, 258, 4096],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_on_off_switch_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.ikea_of_sweden_tradfri_on_off_switch_77665544_power",
            }
        },
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI on/off switch",
        "node_descriptor": b"\x02@\x80|\x11RR\x00\x00,R\x00\x00",
        "zha_quirks": "IkeaTradfriRemote2Btn",
    },
    {
        "device_no": 25,
        "endpoints": {
            1: {
                "device_type": 2096,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 2821, 4096],
                "out_clusters": [3, 4, 5, 6, 8, 25, 4096],
                "profile_id": 49246,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_remote_control_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.ikea_of_sweden_tradfri_remote_control_77665544_power",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI remote control",
        "node_descriptor": b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "IkeaTradfriRemote",
    },
    {
        "device_no": 26,
        "endpoints": {
            1: {
                "device_type": 8,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 9, 2821, 4096, 64636],
                "out_clusters": [25, 32, 4096],
                "profile_id": 260,
            },
            242: {
                "device_type": 97,
                "endpoint_id": 242,
                "in_clusters": [33],
                "out_clusters": [33],
                "profile_id": 41440,
            },
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI signal repeater",
        "node_descriptor": b"\x01@\x8e|\x11RR\x00\x00,R\x00\x00",
    },
    {
        "device_no": 27,
        "endpoints": {
            1: {
                "device_type": 2064,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 2821, 4096],
                "out_clusters": [3, 4, 6, 8, 25, 4096],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_wireless_dimmer_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.ikea_of_sweden_tradfri_wireless_dimmer_77665544_power",
            }
        },
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI wireless dimmer",
        "node_descriptor": b"\x02@\x80|\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 28,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 260,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6, 8],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.jasco_products_45852_77665544_level_on_off",
            "sensor.jasco_products_45852_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.jasco_products_45852_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.jasco_products_45852_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019", "2:0x0006", "2:0x0008"],
        "manufacturer": "Jasco Products",
        "model": "45852",
        "node_descriptor": b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        "device_no": 29,
        "endpoints": {
            1: {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.jasco_products_45856_77665544_on_off",
            "sensor.jasco_products_45856_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.jasco_products_45856_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.jasco_products_45856_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019", "2:0x0006"],
        "manufacturer": "Jasco Products",
        "model": "45856",
        "node_descriptor": b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        "device_no": 30,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 260,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6, 8],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.jasco_products_45857_77665544_level_on_off",
            "sensor.jasco_products_45857_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.jasco_products_45857_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.jasco_products_45857_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019", "2:0x0006", "2:0x0008"],
        "manufacturer": "Jasco Products",
        "model": "45857",
        "node_descriptor": b"\x01@\x8e$\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        "device_no": 31,
        "endpoints": {
            1: {
                "device_type": 3,
                "endpoint_id": 1,
                "in_clusters": [
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
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "cover.keen_home_inc_sv02_610_mp_1_3_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_power",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_temperature",
        ],
        "entity_map": {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "KeenVent",
                "entity_id": "cover.keen_home_inc_sv02_610_mp_1_3_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                "channels": ["pressure"],
                "entity_class": "Pressure",
                "entity_id": "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_pressure",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-610-MP-1.3",
        "node_descriptor": b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
    },
    {
        "device_no": 32,
        "endpoints": {
            1: {
                "device_type": 3,
                "endpoint_id": 1,
                "in_clusters": [
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
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "cover.keen_home_inc_sv02_612_mp_1_2_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_pressure",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_temperature",
        ],
        "entity_map": {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "KeenVent",
                "entity_id": "cover.keen_home_inc_sv02_612_mp_1_2_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                "channels": ["pressure"],
                "entity_class": "Pressure",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_pressure",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-612-MP-1.2",
        "node_descriptor": b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
    },
    {
        "device_no": 33,
        "endpoints": {
            1: {
                "device_type": 3,
                "endpoint_id": 1,
                "in_clusters": [
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
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "cover.keen_home_inc_sv02_612_mp_1_3_77665544_level_on_off",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_temperature",
        ],
        "entity_map": {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "KeenVent",
                "entity_id": "cover.keen_home_inc_sv02_612_mp_1_3_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                "channels": ["pressure"],
                "entity_class": "Pressure",
                "entity_id": "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_pressure",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-612-MP-1.3",
        "node_descriptor": b"\x02@\x80[\x11RR\x00\x00*R\x00\x00",
        "zha_quirks": "KeenHomeSmartVent",
    },
    {
        "device_no": 34,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 514],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "fan.king_of_fans_inc_hbuniversalcfremote_77665544_fan",
            "light.king_of_fans_inc_hbuniversalcfremote_77665544_level_on_off",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.king_of_fans_inc_hbuniversalcfremote_77665544_level_on_off",
            },
            ("fan", "00:11:22:33:44:55:66:77-1-514"): {
                "channels": ["fan"],
                "entity_class": "ZhaFan",
                "entity_id": "fan.king_of_fans_inc_hbuniversalcfremote_77665544_fan",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "King Of Fans,  Inc.",
        "model": "HBUniversalCFRemote",
        "node_descriptor": b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CeilingFan",
    },
    {
        "device_no": 35,
        "endpoints": {
            1: {
                "device_type": 2048,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4096, 64769],
                "out_clusters": [3, 4, 6, 8, 25, 768, 4096],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lds_zbt_cctswitch_d0001_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lds_zbt_cctswitch_d0001_77665544_power",
            }
        },
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0019", "1:0x0300"],
        "manufacturer": "LDS",
        "model": "ZBT-CCTSwitch-D0001",
        "node_descriptor": b"\x02@\x80h\x11RR\x00\x00,R\x00\x00",
        "zha_quirks": "CCTSwitch",
    },
    {
        "device_no": 36,
        "endpoints": {
            1: {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_a19_rgbw_77665544_level_light_color_on_off"],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ledvance_a19_rgbw_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LEDVANCE",
        "model": "A19 RGBW",
        "node_descriptor": b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 37,
        "endpoints": {
            1: {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_flex_rgbw_77665544_level_light_color_on_off"],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ledvance_flex_rgbw_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LEDVANCE",
        "model": "FLEX RGBW",
        "node_descriptor": b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 38,
        "endpoints": {
            1: {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 2821, 64513, 64520],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": ["switch.ledvance_plug_77665544_on_off"],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.ledvance_plug_77665544_on_off",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LEDVANCE",
        "model": "PLUG",
        "node_descriptor": b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 39,
        "endpoints": {
            1: {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_rt_rgbw_77665544_level_light_color_on_off"],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.ledvance_rt_rgbw_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LEDVANCE",
        "model": "RT RGBW",
        "node_descriptor": b"\x01@\x8e\x89\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 40,
        "endpoints": {
            1: {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 2, 3, 4, 5, 6, 10, 16, 2820],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 9,
                "endpoint_id": 2,
                "in_clusters": [12],
                "out_clusters": [4, 12],
                "profile_id": 260,
            },
            3: {
                "device_type": 83,
                "endpoint_id": 3,
                "in_clusters": [12],
                "out_clusters": [12],
                "profile_id": 260,
            },
            100: {
                "device_type": 263,
                "endpoint_id": 100,
                "in_clusters": [15],
                "out_clusters": [4, 15],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input",
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input_2",
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement",
            "switch.lumi_lumi_plug_maus01_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.lumi_lumi_plug_maus01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-12"): {
                "channels": ["analog_input"],
                "entity_class": "AnalogInput",
                "entity_id": "sensor.lumi_lumi_plug_maus01_77665544_analog_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-12"): {
                "channels": ["analog_input"],
                "entity_class": "AnalogInput",
                "entity_id": "sensor.lumi_lumi_plug_maus01_77665544_analog_input_2",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.plug.maus01",
        "node_descriptor": b"\x01@\x8e_\x11\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "Plug",
    },
    {
        "device_no": 41,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 2, 3, 4, 5, 6, 10, 12, 16, 2820],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 257,
                "endpoint_id": 2,
                "in_clusters": [4, 5, 6, 16],
                "out_clusters": [],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.lumi_lumi_relay_c2acn01_77665544_on_off",
            "light.lumi_lumi_relay_c2acn01_77665544_on_off_2",
            "sensor.lumi_lumi_relay_c2acn01_77665544_analog_input",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.lumi_lumi_relay_c2acn01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-12"): {
                "channels": ["analog_input"],
                "entity_class": "AnalogInput",
                "entity_id": "sensor.lumi_lumi_relay_c2acn01_77665544_analog_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.lumi_lumi_relay_c2acn01_77665544_on_off_2",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.relay.c2acn01",
        "node_descriptor": b"\x01@\x8e7\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "Relay",
    },
    {
        "device_no": 42,
        "endpoints": {
            1: {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 18, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            2: {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            3: {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 12, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input",
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_2",
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_3",
            "sensor.lumi_lumi_remote_b186acn01_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_remote_b186acn01_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_2",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_3",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b186acn01",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "RemoteB186ACN01",
    },
    {
        "device_no": 43,
        "endpoints": {
            1: {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 18, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            2: {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            3: {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 12, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input",
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_2",
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_3",
            "sensor.lumi_lumi_remote_b286acn01_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_remote_b286acn01_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_3",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_2",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b286acn01",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "RemoteB286ACN01",
    },
    {
        "device_no": 44,
        "endpoints": {
            1: {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            2: {
                "device_type": -1,
                "endpoint_id": 2,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            3: {
                "device_type": -1,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            4: {
                "device_type": -1,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            5: {
                "device_type": -1,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            6: {
                "device_type": -1,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0300"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b286opcn01",
        "node_descriptor": b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 45,
        "endpoints": {
            1: {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            2: {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
            3: {
                "device_type": -1,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            4: {
                "device_type": -1,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            5: {
                "device_type": -1,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            6: {
                "device_type": -1,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b486opcn01",
        "node_descriptor": b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 46,
        "endpoints": {
            1: {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            }
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0300"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b686opcn01",
        "node_descriptor": b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 47,
        "endpoints": {
            1: {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            2: {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
            3: {
                "device_type": None,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            4: {
                "device_type": None,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            5: {
                "device_type": None,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            6: {
                "device_type": None,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
        },
        "entities": [],
        "entity_map": {},
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0300", "2:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b686opcn01",
        "node_descriptor": b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 48,
        "endpoints": {
            8: {
                "device_type": 256,
                "endpoint_id": 8,
                "in_clusters": [0, 6],
                "out_clusters": [0, 6],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.lumi_lumi_router_77665544_on_off",
            },
        },
        "event_channels": ["8:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.router",
        "node_descriptor": b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 49,
        "endpoints": {
            8: {
                "device_type": 256,
                "endpoint_id": 8,
                "in_clusters": [0, 6, 11, 17],
                "out_clusters": [0, 6],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.lumi_lumi_router_77665544_on_off",
            },
        },
        "event_channels": ["8:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.router",
        "node_descriptor": b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 50,
        "endpoints": {
            8: {
                "device_type": 256,
                "endpoint_id": 8,
                "in_clusters": [0, 6, 17],
                "out_clusters": [0, 6],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_router_77665544_on_off",
            "light.lumi_lumi_router_77665544_on_off",
        ],
        "entity_map": {
            ("binary_sensor", "00:11:22:33:44:55:66:77-8-6"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.lumi_lumi_router_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-8"): {
                "channels": ["on_off", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.lumi_lumi_router_77665544_on_off",
            },
        },
        "event_channels": ["8:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.router",
        "node_descriptor": b"\x01@\x8e_\x11P\xa0\x00\x00\x00\xa0\x00\x00",
    },
    {
        "device_no": 51,
        "endpoints": {
            1: {
                "device_type": 262,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1024],
                "out_clusters": [3],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lumi_lumi_sen_ill_mgl01_77665544_illuminance"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                "channels": ["illuminance"],
                "entity_class": "Illuminance",
                "entity_id": "sensor.lumi_lumi_sen_ill_mgl01_77665544_illuminance",
            }
        },
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.sen_ill.mgl01",
        "node_descriptor": b"\x02@\x84n\x12\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 52,
        "endpoints": {
            1: {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 18, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            2: {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            3: {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 12, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input",
            "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input_2",
            "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input_3",
            "sensor.lumi_lumi_sensor_86sw1_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_86sw1_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input_3",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input_2",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_86sw1_77665544_multistate_input",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_86sw1",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "RemoteB186ACN01",
    },
    {
        "device_no": 53,
        "endpoints": {
            1: {
                "device_type": 28417,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25],
                "out_clusters": [0, 3, 4, 5, 18, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 28418,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            3: {
                "device_type": 28419,
                "endpoint_id": 3,
                "in_clusters": [3, 12],
                "out_clusters": [3, 4, 5, 12],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_analog_input",
            "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_multistate_input",
            "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-2-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_multistate_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-12"): {
                "channels": ["analog_input"],
                "entity_class": "AnalogInput",
                "entity_id": "sensor.lumi_lumi_sensor_cube_aqgl01_77665544_analog_input",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_cube.aqgl01",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "CubeAQGL01",
    },
    {
        "device_no": 54,
        "endpoints": {
            1: {
                "device_type": 24322,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 1026, 1029, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            2: {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            3: {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 12],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_sensor_ht_77665544_humidity",
            "sensor.lumi_lumi_sensor_ht_77665544_power",
            "sensor.lumi_lumi_sensor_ht_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_ht_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.lumi_lumi_sensor_ht_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                "channels": ["humidity"],
                "entity_class": "Humidity",
                "entity_id": "sensor.lumi_lumi_sensor_ht_77665544_humidity",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005", "3:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_ht",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "Weather",
    },
    {
        "device_no": 55,
        "endpoints": {
            1: {
                "device_type": 2128,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_magnet_77665544_on_off",
            "sensor.lumi_lumi_sensor_magnet_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_magnet_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.lumi_lumi_sensor_magnet_77665544_on_off",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_magnet",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "Magnet",
    },
    {
        "device_no": 56,
        "endpoints": {
            1: {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 65535],
                "out_clusters": [0, 4, 6, 65535],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_magnet_aq2_77665544_on_off",
            "sensor.lumi_lumi_sensor_magnet_aq2_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_magnet_aq2_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Opening",
                "entity_id": "binary_sensor.lumi_lumi_sensor_magnet_aq2_77665544_on_off",
            },
        },
        "event_channels": ["1:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_magnet.aq2",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "MagnetAQ2",
    },
    {
        "device_no": 57,
        "endpoints": {
            1: {
                "device_type": 263,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1024, 1030, 1280, 65535],
                "out_clusters": [0, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_ias_zone",
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_occupancy",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_illuminance",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_motion_aq2_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                "channels": ["illuminance"],
                "entity_class": "Illuminance",
                "entity_id": "sensor.lumi_lumi_sensor_motion_aq2_77665544_illuminance",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1030"): {
                "channels": ["occupancy"],
                "entity_class": "Occupancy",
                "entity_id": "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_occupancy",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_motion.aq2",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "MotionAQ2",
    },
    {
        "device_no": 58,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 12, 18, 1280],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_smoke_77665544_ias_zone",
            "sensor.lumi_lumi_sensor_smoke_77665544_analog_input",
            "sensor.lumi_lumi_sensor_smoke_77665544_multistate_input",
            "sensor.lumi_lumi_sensor_smoke_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_smoke_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-12"): {
                "channels": ["analog_input"],
                "entity_class": "AnalogInput",
                "entity_id": "sensor.lumi_lumi_sensor_smoke_77665544_analog_input",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_smoke_77665544_multistate_input",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.lumi_lumi_sensor_smoke_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_smoke",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "MijiaHoneywellSmokeDetectorSensor",
    },
    {
        "device_no": 59,
        "endpoints": {
            1: {
                "device_type": 6,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [0, 4, 5, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lumi_lumi_sensor_switch_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_switch_77665544_power",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "MijaButton",
    },
    {
        "device_no": 60,
        "endpoints": {
            1: {
                "device_type": 6,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 65535],
                "out_clusters": [0, 4, 6, 65535],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lumi_lumi_sensor_switch_aq2_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_switch_aq2_77665544_power",
            }
        },
        "event_channels": ["1:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch.aq2",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "SwitchAQ2",
    },
    {
        "device_no": 61,
        "endpoints": {
            1: {
                "device_type": 6,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 18],
                "out_clusters": [0, 6],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.lumi_lumi_sensor_switch_aq3_77665544_multistate_input",
            "sensor.lumi_lumi_sensor_switch_aq3_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_switch_aq3_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-18"): {
                "channels": ["multistate_input"],
                "entity_class": "Text",
                "entity_id": "sensor.lumi_lumi_sensor_switch_aq3_77665544_multistate_input",
            },
        },
        "event_channels": ["1:0x0006"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch.aq3",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "SwitchAQ3",
    },
    {
        "device_no": 62,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1280],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_wleak_aq1_77665544_ias_zone",
            "sensor.lumi_lumi_sensor_wleak_aq1_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_sensor_wleak_aq1_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.lumi_lumi_sensor_wleak_aq1_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_wleak.aq1",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "LeakAQ1",
    },
    {
        "device_no": 63,
        "endpoints": {
            1: {
                "device_type": 10,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 257, 1280],
                "out_clusters": [0, 3, 4, 5, 25],
                "profile_id": 260,
            },
            2: {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "binary_sensor.lumi_lumi_vibration_aq1_77665544_ias_zone",
            "lock.lumi_lumi_vibration_aq1_77665544_door_lock",
            "sensor.lumi_lumi_vibration_aq1_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_vibration_aq1_77665544_power",
            },
            ("lock", "00:11:22:33:44:55:66:77-1-257"): {
                "channels": ["door_lock"],
                "entity_class": "ZhaDoorLock",
                "entity_id": "lock.lumi_lumi_vibration_aq1_77665544_door_lock",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.lumi_lumi_vibration_aq1_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0019", "2:0x0005"],
        "manufacturer": "LUMI",
        "model": "lumi.vibration.aq1",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "VibrationAQ1",
    },
    {
        "device_no": 64,
        "endpoints": {
            1: {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1026, 1027, 1029, 65535],
                "out_clusters": [0, 4, 65535],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.lumi_lumi_weather_77665544_humidity",
            "sensor.lumi_lumi_weather_77665544_power",
            "sensor.lumi_lumi_weather_77665544_pressure",
            "sensor.lumi_lumi_weather_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.lumi_lumi_weather_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.lumi_lumi_weather_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1027"): {
                "channels": ["pressure"],
                "entity_class": "Pressure",
                "entity_id": "sensor.lumi_lumi_weather_77665544_pressure",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1029"): {
                "channels": ["humidity"],
                "entity_class": "Humidity",
                "entity_id": "sensor.lumi_lumi_weather_77665544_humidity",
            },
        },
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.weather",
        "node_descriptor": b"\x02@\x807\x10\x7fd\x00\x00\x00d\x00\x00",
        "zha_quirks": "Weather",
    },
    {
        "device_no": 65,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1280],
                "out_clusters": [],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.nyce_3010_77665544_ias_zone",
            "sensor.nyce_3010_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.nyce_3010_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.nyce_3010_77665544_ias_zone",
            },
        },
        "event_channels": [],
        "manufacturer": "NYCE",
        "model": "3010",
        "node_descriptor": b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 66,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1280],
                "out_clusters": [],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.nyce_3014_77665544_ias_zone",
            "sensor.nyce_3014_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.nyce_3014_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.nyce_3014_77665544_ias_zone",
            },
        },
        "event_channels": [],
        "manufacturer": "NYCE",
        "model": "3014",
        "node_descriptor": b"\x02@\x80\xb9\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 67,
        "endpoints": {
            1: {
                "device_type": 5,
                "endpoint_id": 1,
                "in_clusters": [10, 25],
                "out_clusters": [1280],
                "profile_id": 260,
            },
            242: {
                "device_type": 100,
                "endpoint_id": 242,
                "in_clusters": [],
                "out_clusters": [33],
                "profile_id": 41440,
            },
        },
        "entities": ["1:0x0019"],
        "entity_map": {},
        "event_channels": [],
        "manufacturer": None,
        "model": None,
        "node_descriptor": b"\x10@\x0f5\x11Y=\x00@\x00=\x00\x00",
    },
    {
        "device_no": 68,
        "endpoints": {
            1: {
                "device_type": 48879,
                "endpoint_id": 1,
                "in_clusters": [],
                "out_clusters": [1280],
                "profile_id": 260,
            }
        },
        "entities": [],
        "entity_map": {},
        "event_channels": [],
        "manufacturer": None,
        "model": None,
        "node_descriptor": b"\x00@\x8f\xcd\xabR\x80\x00\x00\x00\x80\x00\x00",
    },
    {
        "device_no": 69,
        "endpoints": {
            3: {
                "device_type": 258,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 64527],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.osram_lightify_a19_rgbw_77665544_level_light_color_on_off"],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.osram_lightify_a19_rgbw_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["3:0x0019"],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY A19 RGBW",
        "node_descriptor": b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        "zha_quirks": "LIGHTIFYA19RGBW",
    },
    {
        "device_no": 70,
        "endpoints": {
            1: {
                "device_type": 1,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 2821],
                "out_clusters": [3, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.osram_lightify_dimming_switch_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.osram_lightify_dimming_switch_77665544_power",
            }
        },
        "event_channels": ["1:0x0006", "1:0x0008", "1:0x0019"],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY Dimming Switch",
        "node_descriptor": b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "CentraLite3130",
    },
    {
        "device_no": 71,
        "endpoints": {
            3: {
                "device_type": 258,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 64527],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.osram_lightify_flex_rgbw_77665544_level_light_color_on_off"
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.osram_lightify_flex_rgbw_77665544_level_light_color_on_off",
            }
        },
        "event_channels": ["3:0x0019"],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY Flex RGBW",
        "node_descriptor": b"\x19@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        "zha_quirks": "FlexRGBW",
    },
    {
        "device_no": 72,
        "endpoints": {
            3: {
                "device_type": 258,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2820, 64527],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.osram_lightify_rt_tunable_white_77665544_level_light_color_on_off",
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-3"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.osram_lightify_rt_tunable_white_77665544_level_light_color_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement",
            },
        },
        "event_channels": ["3:0x0019"],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY RT Tunable White",
        "node_descriptor": b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
        "zha_quirks": "A19TunableWhite",
    },
    {
        "device_no": 73,
        "endpoints": {
            3: {
                "device_type": 16,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 2820, 4096, 64527],
                "out_clusters": [25],
                "profile_id": 49246,
            }
        },
        "entities": [
            "sensor.osram_plug_01_77665544_electrical_measurement",
            "switch.osram_plug_01_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-3"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.osram_plug_01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-3-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.osram_plug_01_77665544_electrical_measurement",
            },
        },
        "event_channels": ["3:0x0019"],
        "manufacturer": "OSRAM",
        "model": "Plug 01",
        "node_descriptor": b"\x01@\x8e\xaa\xbb@\x00\x00\x00\x00\x00\x00\x03",
    },
    {
        "device_no": 74,
        "endpoints": {
            1: {
                "device_type": 2064,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 32, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 25, 768, 4096],
                "profile_id": 260,
            },
            2: {
                "device_type": 2064,
                "endpoint_id": 2,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            3: {
                "device_type": 2064,
                "endpoint_id": 3,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            4: {
                "device_type": 2064,
                "endpoint_id": 4,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            5: {
                "device_type": 2064,
                "endpoint_id": 5,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            6: {
                "device_type": 2064,
                "endpoint_id": 6,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
        },
        "entities": ["sensor.osram_switch_4x_lightify_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.osram_switch_4x_lightify_77665544_power",
            }
        },
        "event_channels": [
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
        "manufacturer": "OSRAM",
        "model": "Switch 4x-LIGHTIFY",
        "node_descriptor": b"\x02@\x80\x0c\x11RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "LightifyX4",
    },
    {
        "device_no": 75,
        "endpoints": {
            1: {
                "device_type": 2096,
                "endpoint_id": 1,
                "in_clusters": [0],
                "out_clusters": [0, 3, 4, 5, 6, 8],
                "profile_id": 49246,
            },
            2: {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 1, 3, 15, 64512],
                "out_clusters": [25],
                "profile_id": 260,
            },
        },
        "entities": ["sensor.philips_rwl020_77665544_power"],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-2-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.philips_rwl020_77665544_power",
            }
        },
        "event_channels": ["1:0x0005", "1:0x0006", "1:0x0008", "2:0x0019"],
        "manufacturer": "Philips",
        "model": "RWL020",
        "node_descriptor": b"\x02@\x80\x0b\x10G-\x00\x00\x00-\x00\x00",
        "zha_quirks": "PhilipsRWL021",
    },
    {
        "device_no": 76,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.samjin_button_77665544_ias_zone",
            "sensor.samjin_button_77665544_power",
            "sensor.samjin_button_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.samjin_button_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.samjin_button_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.samjin_button_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Samjin",
        "model": "button",
        "node_descriptor": b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        "zha_quirks": "SamjinButton",
    },
    {
        "device_no": 77,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 64514],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.samjin_multi_77665544_ias_zone",
            "binary_sensor.samjin_multi_77665544_manufacturer_specific",
            "sensor.samjin_multi_77665544_power",
            "sensor.samjin_multi_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.samjin_multi_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.samjin_multi_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.samjin_multi_77665544_ias_zone",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-64514"): {
                "channels": ["manufacturer_specific"],
                "entity_class": "BinarySensor",
                "entity_id": "binary_sensor.samjin_multi_77665544_manufacturer_specific",
                "default_match": True,
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Samjin",
        "model": "multi",
        "node_descriptor": b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
        "zha_quirks": "SmartthingsMultiPurposeSensor",
    },
    {
        "device_no": 78,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.samjin_water_77665544_ias_zone",
            "sensor.samjin_water_77665544_power",
            "sensor.samjin_water_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.samjin_water_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.samjin_water_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.samjin_water_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Samjin",
        "model": "water",
        "node_descriptor": b"\x02@\x80A\x12RR\x00\x00,R\x00\x00",
    },
    {
        "device_no": 79,
        "endpoints": {
            1: {
                "device_type": 0,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 6, 2820, 2821],
                "out_clusters": [0, 1, 3, 4, 5, 6, 25, 2820, 2821],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement",
            "switch.securifi_ltd_unk_model_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.securifi_ltd_unk_model_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.securifi_ltd_unk_model_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0005", "1:0x0006", "1:0x0019"],
        "manufacturer": "Securifi Ltd.",
        "model": None,
        "node_descriptor": b"\x01@\x8e\x02\x10RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 80,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.sercomm_corp_sz_dws04n_sf_77665544_ias_zone",
            "sensor.sercomm_corp_sz_dws04n_sf_77665544_power",
            "sensor.sercomm_corp_sz_dws04n_sf_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.sercomm_corp_sz_dws04n_sf_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.sercomm_corp_sz_dws04n_sf_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.sercomm_corp_sz_dws04n_sf_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-DWS04N_SF",
        "node_descriptor": b"\x02@\x801\x11R\xff\x00\x00\x00\xff\x00\x00",
    },
    {
        "device_no": 81,
        "endpoints": {
            1: {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 6, 1794, 2820, 2821],
                "out_clusters": [3, 10, 25, 2821],
                "profile_id": 260,
            },
            2: {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.sercomm_corp_sz_esw01_77665544_on_off",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement",
            "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.sercomm_corp_sz_esw01_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019", "2:0x0006"],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-ESW01",
        "node_descriptor": b"\x01@\x8e1\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 82,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1024, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.sercomm_corp_sz_pir04_77665544_ias_zone",
            "sensor.sercomm_corp_sz_pir04_77665544_illuminance",
            "sensor.sercomm_corp_sz_pir04_77665544_power",
            "sensor.sercomm_corp_sz_pir04_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.sercomm_corp_sz_pir04_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1024"): {
                "channels": ["illuminance"],
                "entity_class": "Illuminance",
                "entity_id": "sensor.sercomm_corp_sz_pir04_77665544_illuminance",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.sercomm_corp_sz_pir04_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.sercomm_corp_sz_pir04_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-PIR04",
        "node_descriptor": b"\x02@\x801\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 83,
        "endpoints": {
            1: {
                "device_type": 2,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 2820, 2821, 65281],
                "out_clusters": [3, 4, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement",
            "switch.sinope_technologies_rm3250zb_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.sinope_technologies_rm3250zb_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.sinope_technologies_rm3250zb_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Sinope Technologies",
        "model": "RM3250ZB",
        "node_descriptor": b"\x11@\x8e\x9c\x11G+\x00\x00*+\x00\x00",
    },
    {
        "device_no": 84,
        "endpoints": {
            1: {
                "device_type": 769,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 513, 516, 1026, 2820, 2821, 65281],
                "out_clusters": [25, 65281],
                "profile_id": 260,
            },
            196: {
                "device_type": 769,
                "endpoint_id": 196,
                "in_clusters": [1],
                "out_clusters": [],
                "profile_id": 49757,
            },
        },
        "entities": [
            "climate.sinope_technologies_th1123zb_77665544_thermostat",
            "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement",
            "sensor.sinope_technologies_th1123zb_77665544_temperature",
        ],
        "entity_map": {
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["thermostat"],
                "entity_class": "Thermostat",
                "entity_id": "climate.sinope_technologies_th1123zb_77665544_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.sinope_technologies_th1123zb_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.sinope_technologies_th1123zb_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Sinope Technologies",
        "model": "TH1123ZB",
        "node_descriptor": b"\x12@\x8c\x9c\x11G+\x00\x00\x00+\x00\x00",
        "zha_quirks": "SinopeTechnologiesThermostat",
    },
    {
        "device_no": 85,
        "endpoints": {
            1: {
                "device_type": 769,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 513, 516, 1026, 2820, 2821, 65281],
                "out_clusters": [25, 65281],
                "profile_id": 260,
            },
            196: {
                "device_type": 769,
                "endpoint_id": 196,
                "in_clusters": [1],
                "out_clusters": [],
                "profile_id": 49757,
            },
        },
        "entities": [
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement",
            "sensor.sinope_technologies_th1124zb_77665544_temperature",
            "climate.sinope_technologies_th1124zb_77665544_thermostat",
        ],
        "entity_map": {
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["thermostat"],
                "entity_class": "Thermostat",
                "entity_id": "climate.sinope_technologies_th1124zb_77665544_thermostat",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.sinope_technologies_th1124zb_77665544_temperature",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Sinope Technologies",
        "model": "TH1124ZB",
        "node_descriptor": b"\x11@\x8e\x9c\x11G+\x00\x00\x00+\x00\x00",
        "zha_quirks": "SinopeTechnologiesThermostat",
    },
    {
        "device_no": 86,
        "endpoints": {
            1: {
                "device_type": 2,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 9, 15, 2820],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.smartthings_outletv4_77665544_electrical_measurement",
            "switch.smartthings_outletv4_77665544_on_off",
        ],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.smartthings_outletv4_77665544_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-2820"): {
                "channels": ["electrical_measurement"],
                "entity_class": "ElectricalMeasurement",
                "entity_id": "sensor.smartthings_outletv4_77665544_electrical_measurement",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "SmartThings",
        "model": "outletv4",
        "node_descriptor": b"\x01@\x8e\n\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 87,
        "endpoints": {
            1: {
                "device_type": 32768,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 15, 32],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": ["device_tracker.smartthings_tagv4_77665544_power"],
        "entity_map": {
            ("device_tracker", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["power"],
                "entity_class": "ZHADeviceScannerEntity",
                "entity_id": "device_tracker.smartthings_tagv4_77665544_power",
            }
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "SmartThings",
        "model": "tagv4",
        "node_descriptor": b"\x02@\x80\n\x11RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "SmartThingsTagV4",
    },
    {
        "device_no": 88,
        "endpoints": {
            1: {
                "device_type": 2,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 25],
                "out_clusters": [],
                "profile_id": 260,
            }
        },
        "entities": ["switch.third_reality_inc_3rss007z_77665544_on_off"],
        "entity_map": {
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.third_reality_inc_3rss007z_77665544_on_off",
            }
        },
        "event_channels": [],
        "manufacturer": "Third Reality, Inc",
        "model": "3RSS007Z",
        "node_descriptor": b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
    },
    {
        "device_no": 89,
        "endpoints": {
            1: {
                "device_type": 2,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 6, 25],
                "out_clusters": [1],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.third_reality_inc_3rss008z_77665544_power",
            "switch.third_reality_inc_3rss008z_77665544_on_off",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.third_reality_inc_3rss008z_77665544_power",
            },
            ("switch", "00:11:22:33:44:55:66:77-1-6"): {
                "channels": ["on_off"],
                "entity_class": "Switch",
                "entity_id": "switch.third_reality_inc_3rss008z_77665544_on_off",
            },
        },
        "event_channels": [],
        "manufacturer": "Third Reality, Inc",
        "model": "3RSS008Z",
        "node_descriptor": b"\x02@\x803\x12\x7fd\x00\x00,d\x00\x00",
        "zha_quirks": "Switch",
    },
    {
        "device_no": 90,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.visonic_mct_340_e_77665544_ias_zone",
            "sensor.visonic_mct_340_e_77665544_power",
            "sensor.visonic_mct_340_e_77665544_temperature",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.visonic_mct_340_e_77665544_power",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1026"): {
                "channels": ["temperature"],
                "entity_class": "Temperature",
                "entity_id": "sensor.visonic_mct_340_e_77665544_temperature",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.visonic_mct_340_e_77665544_ias_zone",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Visonic",
        "model": "MCT-340 E",
        "node_descriptor": b"\x02@\x80\x11\x10RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "MCT340E",
    },
    {
        "device_no": 91,
        "endpoints": {
            1: {
                "device_type": 769,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 32, 513, 514, 516, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "climate.zen_within_zen_01_77665544_fan_thermostat",
            "sensor.zen_within_zen_01_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.zen_within_zen_01_77665544_power",
            },
            ("climate", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["thermostat", "fan"],
                "entity_class": "ZenWithinThermostat",
                "entity_id": "climate.zen_within_zen_01_77665544_fan_thermostat",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "Zen Within",
        "model": "Zen-01",
        "node_descriptor": b"\x02@\x80X\x11R\x80\x00\x00\x00\x80\x00\x00",
    },
    {
        "device_no": 92,
        "endpoints": {
            1: {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 4, 5, 6, 10],
                "out_clusters": [25],
                "profile_id": 260,
            },
            2: {
                "device_type": 256,
                "endpoint_id": 2,
                "in_clusters": [4, 5, 6],
                "out_clusters": [],
                "profile_id": 260,
            },
            3: {
                "device_type": 256,
                "endpoint_id": 3,
                "in_clusters": [4, 5, 6],
                "out_clusters": [],
                "profile_id": 260,
            },
            4: {
                "device_type": 256,
                "endpoint_id": 4,
                "in_clusters": [4, 5, 6],
                "out_clusters": [],
                "profile_id": 260,
            },
        },
        "entities": [
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_2",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_3",
            "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_4",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_4",
            },
            ("light", "00:11:22:33:44:55:66:77-2"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_3",
            },
            ("light", "00:11:22:33:44:55:66:77-3"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.tyzb01_ns1ndbww_ts0004_77665544_on_off",
            },
            ("light", "00:11:22:33:44:55:66:77-4"): {
                "channels": ["on_off"],
                "entity_class": "Light",
                "entity_id": "light.tyzb01_ns1ndbww_ts0004_77665544_on_off_2",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "_TYZB01_ns1ndbww",
        "model": "TS0004",
        "node_descriptor": b"\x01@\x8e\x02\x10R\x00\x02\x00,\x00\x02\x00",
    },
    {
        "device_no": 93,
        "endpoints": {
            1: {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 21, 32, 1280, 2821],
                "out_clusters": [],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.netvox_z308e3ed_77665544_ias_zone",
            "sensor.netvox_z308e3ed_77665544_power",
        ],
        "entity_map": {
            ("sensor", "00:11:22:33:44:55:66:77-1-1"): {
                "channels": ["power"],
                "entity_class": "Battery",
                "entity_id": "sensor.netvox_z308e3ed_77665544_power",
            },
            ("binary_sensor", "00:11:22:33:44:55:66:77-1-1280"): {
                "channels": ["ias_zone"],
                "entity_class": "IASZone",
                "entity_id": "binary_sensor.netvox_z308e3ed_77665544_ias_zone",
            },
        },
        "event_channels": [],
        "manufacturer": "netvox",
        "model": "Z308E3ED",
        "node_descriptor": b"\x02@\x80\x9f\x10RR\x00\x00\x00R\x00\x00",
        "zha_quirks": "Z308E3ED",
    },
    {
        "device_no": 94,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.sengled_e11_g13_77665544_level_on_off",
            "sensor.sengled_e11_g13_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.sengled_e11_g13_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.sengled_e11_g13_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "sengled",
        "model": "E11-G13",
        "node_descriptor": b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 95,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.sengled_e12_n14_77665544_level_on_off",
            "sensor.sengled_e12_n14_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.sengled_e12_n14_77665544_level_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.sengled_e12_n14_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "sengled",
        "model": "E12-N14",
        "node_descriptor": b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 96,
        "endpoints": {
            1: {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 1794, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "light.sengled_z01_a19nae26_77665544_level_light_color_on_off",
            "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering",
        ],
        "entity_map": {
            ("light", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "light_color", "on_off"],
                "entity_class": "Light",
                "entity_id": "light.sengled_z01_a19nae26_77665544_level_light_color_on_off",
            },
            ("sensor", "00:11:22:33:44:55:66:77-1-1794"): {
                "channels": ["smartenergy_metering"],
                "entity_class": "SmartEnergyMetering",
                "entity_id": "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering",
            },
        },
        "event_channels": ["1:0x0019"],
        "manufacturer": "sengled",
        "model": "Z01-A19NAE26",
        "node_descriptor": b"\x02@\x8c`\x11RR\x00\x00\x00R\x00\x00",
    },
    {
        "device_no": 97,
        "endpoints": {
            1: {
                "device_type": 512,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 10, 21, 256, 64544, 64545],
                "out_clusters": [3, 64544],
                "profile_id": 260,
            }
        },
        "entities": ["cover.unk_manufacturer_unk_model_77665544_level_on_off_shade"],
        "entity_map": {
            ("cover", "00:11:22:33:44:55:66:77-1"): {
                "channels": ["level", "on_off", "shade"],
                "entity_class": "Shade",
                "entity_id": "cover.unk_manufacturer_unk_model_77665544_level_on_off_shade",
            }
        },
        "event_channels": [],
        "manufacturer": "unk_manufacturer",
        "model": "unk_model",
        "node_descriptor": b"\x01@\x8e\x10\x11RR\x00\x00\x00R\x00\x00",
    },
]
