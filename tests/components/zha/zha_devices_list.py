"""Example Zigbee Devices."""

DEVICES = [
    {
        "endpoints": {
            "1": {
                "device_type": 2080,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4096, 64716],
                "out_clusters": [3, 4, 6, 8, 4096, 64716],
                "profile_id": 260,
            }
        },
        "entities": [],
        "event_channels": [6, 8],
        "manufacturer": "ADUROLIGHT",
        "model": "Adurolight_NCC",
    },
    {
        "endpoints": {
            "5": {
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
        "event_channels": [],
        "manufacturer": "Bosch",
        "model": "ISW-ZPR1-WP13",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 2821],
                "out_clusters": [3, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.centralite_3130_77665544_on_off",
            "sensor.centralite_3130_77665544_power",
        ],
        "event_channels": [6, 8],
        "manufacturer": "CentraLite",
        "model": "3130",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794, 2820, 2821, 64515],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.centralite_3210_l_77665544_smartenergy_metering",
            "sensor.centralite_3210_l_77665544_electrical_measurement",
            "switch.centralite_3210_l_77665544_on_off",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "3210-L",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 770,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 2821, 64581],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.centralite_3310_s_77665544_power",
            "sensor.centralite_3310_s_77665544_temperature",
            "sensor.centralite_3310_s_77665544_manufacturer_specific",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "3310-S",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64527],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3315_s_77665544_ias_zone",
            "sensor.centralite_3315_s_77665544_temperature",
            "sensor.centralite_3315_s_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "3315-S",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64527],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3320_l_77665544_ias_zone",
            "sensor.centralite_3320_l_77665544_temperature",
            "sensor.centralite_3320_l_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "3320-L",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 263,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821, 64582],
                "out_clusters": [3],
                "profile_id": 49887,
            },
        },
        "entities": [
            "binary_sensor.centralite_3326_l_77665544_ias_zone",
            "sensor.centralite_3326_l_77665544_temperature",
            "sensor.centralite_3326_l_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "3326-L",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 263,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 1030, 2821],
                "out_clusters": [3],
                "profile_id": 260,
            },
        },
        "entities": [
            "binary_sensor.centralite_motion_sensor_a_77665544_occupancy",
            "binary_sensor.centralite_motion_sensor_a_77665544_ias_zone",
            "sensor.centralite_motion_sensor_a_77665544_temperature",
            "sensor.centralite_motion_sensor_a_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "CentraLite",
        "model": "Motion Sensor-A",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794],
                "out_clusters": [0],
                "profile_id": 260,
            },
            "4": {
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
        "event_channels": [],
        "manufacturer": "ClimaxTechnology",
        "model": "PSMP5_00.00.02.02TC",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "ClimaxTechnology",
        "model": "SD8SC_00.00.03.12TC",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "ClimaxTechnology",
        "model": "WS15_00.00.03.03TC",
    },
    {
        "endpoints": {
            "11": {
                "device_type": 528,
                "endpoint_id": 11,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768],
                "out_clusters": [],
                "profile_id": 49246,
            },
            "13": {
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
        "event_channels": [],
        "manufacturer": "Feibit Inc co.",
        "model": "FB56-ZCW08KU1.1",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1027,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 9, 1280, 1282],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.heiman_warningdevice_77665544_ias_zone",
            "sensor.heiman_warningdevice_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "Heiman",
        "model": "WarningDevice",
    },
    {
        "endpoints": {
            "6": {
                "device_type": 1026,
                "endpoint_id": 6,
                "in_clusters": [0, 1, 3, 32, 1024, 1026, 1280],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.hivehome_com_mot003_77665544_temperature",
            "sensor.hivehome_com_mot003_77665544_power",
            "sensor.hivehome_com_mot003_77665544_illuminance",
            "binary_sensor.hivehome_com_mot003_77665544_ias_zone",
        ],
        "event_channels": [],
        "manufacturer": "HiveHome.com",
        "model": "MOT003",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 268,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 4096, 64636],
                "out_clusters": [5, 25, 32, 4096],
                "profile_id": 260,
            },
            "242": {
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
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E12 WS opal 600lm",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 CWS opal 600lm",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 W opal 1000lm",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 WS opal 980lm",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI bulb E26 opal 1000lm",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 266,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 64636],
                "out_clusters": [5, 25, 32],
                "profile_id": 260,
            }
        },
        "entities": ["switch.ikea_of_sweden_tradfri_control_outlet_77665544_on_off"],
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI control outlet",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [6],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI motion sensor",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2080,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 32, 4096, 64636],
                "out_clusters": [3, 4, 6, 8, 25, 258, 4096],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_on_off_switch_77665544_power"],
        "event_channels": [6, 8],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI on/off switch",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2096,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 2821, 4096],
                "out_clusters": [3, 4, 5, 6, 8, 25, 4096],
                "profile_id": 49246,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_remote_control_77665544_power"],
        "event_channels": [6, 8],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI remote control",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 8,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 9, 2821, 4096, 64636],
                "out_clusters": [25, 32, 4096],
                "profile_id": 260,
            },
            "242": {
                "device_type": 97,
                "endpoint_id": 242,
                "in_clusters": [33],
                "out_clusters": [33],
                "profile_id": 41440,
            },
        },
        "entities": [],
        "event_channels": [],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI signal repeater",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2064,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 9, 2821, 4096],
                "out_clusters": [3, 4, 6, 8, 25, 4096],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.ikea_of_sweden_tradfri_wireless_dimmer_77665544_power"],
        "event_channels": [6, 8],
        "manufacturer": "IKEA of Sweden",
        "model": "TRADFRI wireless dimmer",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 260,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6, 8],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.jasco_products_45852_77665544_smartenergy_metering",
            "light.jasco_products_45852_77665544_level_on_off",
        ],
        "event_channels": [6, 8],
        "manufacturer": "Jasco Products",
        "model": "45852",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.jasco_products_45856_77665544_smartenergy_metering",
            "switch.jasco_products_45856_77665544_on_off",
            "light.jasco_products_45856_77665544_on_off",
        ],
        "event_channels": [6],
        "manufacturer": "Jasco Products",
        "model": "45856",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 260,
                "endpoint_id": 2,
                "in_clusters": [0, 3, 2821],
                "out_clusters": [3, 6, 8],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.jasco_products_45857_77665544_smartenergy_metering",
            "light.jasco_products_45857_77665544_level_on_off",
        ],
        "event_channels": [6, 8],
        "manufacturer": "Jasco Products",
        "model": "45857",
    },
    {
        "endpoints": {
            "1": {
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
            "binary_sensor.keen_home_inc_sv02_610_mp_1_3_77665544_manufacturer_specific",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_temperature",
            "sensor.keen_home_inc_sv02_610_mp_1_3_77665544_power",
            "light.keen_home_inc_sv02_610_mp_1_3_77665544_level_on_off",
        ],
        "event_channels": [],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-610-MP-1.3",
    },
    {
        "endpoints": {
            "1": {
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
            "binary_sensor.keen_home_inc_sv02_612_mp_1_2_77665544_manufacturer_specific",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_temperature",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_2_77665544_pressure",
            "light.keen_home_inc_sv02_612_mp_1_2_77665544_level_on_off",
        ],
        "event_channels": [],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-612-MP-1.2",
    },
    {
        "endpoints": {
            "1": {
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
            "binary_sensor.keen_home_inc_sv02_612_mp_1_3_77665544_manufacturer_specific",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_pressure",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_power",
            "sensor.keen_home_inc_sv02_612_mp_1_3_77665544_temperature",
            "light.keen_home_inc_sv02_612_mp_1_3_77665544_level_on_off",
        ],
        "event_channels": [],
        "manufacturer": "Keen Home Inc",
        "model": "SV02-612-MP-1.3",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 14,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 514],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "fan.king_of_fans_inc_hbuniversalcfremote_77665544_fan",
            "switch.king_of_fans_inc_hbuniversalcfremote_77665544_on_off",
        ],
        "event_channels": [],
        "manufacturer": "King Of Fans,  Inc.",
        "model": "HBUniversalCFRemote",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_a19_rgbw_77665544_level_light_color_on_off"],
        "event_channels": [],
        "manufacturer": "LEDVANCE",
        "model": "A19 RGBW",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_flex_rgbw_77665544_level_light_color_on_off"],
        "event_channels": [],
        "manufacturer": "LEDVANCE",
        "model": "FLEX RGBW",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 2821, 64513, 64520],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": ["switch.ledvance_plug_77665544_on_off"],
        "event_channels": [],
        "manufacturer": "LEDVANCE",
        "model": "PLUG",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.ledvance_rt_rgbw_77665544_level_light_color_on_off"],
        "event_channels": [],
        "manufacturer": "LEDVANCE",
        "model": "RT RGBW",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 81,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 2, 3, 4, 5, 6, 10, 16, 2820],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            "100": {
                "device_type": 263,
                "endpoint_id": 100,
                "in_clusters": [15],
                "out_clusters": [4, 15],
                "profile_id": 260,
            },
            "2": {
                "device_type": 9,
                "endpoint_id": 2,
                "in_clusters": [12],
                "out_clusters": [4, 12],
                "profile_id": 260,
            },
            "3": {
                "device_type": 83,
                "endpoint_id": 3,
                "in_clusters": [12],
                "out_clusters": [12],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_plug_maus01_77665544_electrical_measurement",
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input",
            "sensor.lumi_lumi_plug_maus01_77665544_analog_input_2",
            "sensor.lumi_lumi_plug_maus01_77665544_power",
            "switch.lumi_lumi_plug_maus01_77665544_on_off",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.plug.maus01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 2, 3, 4, 5, 6, 10, 12, 16, 2820],
                "out_clusters": [10, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 257,
                "endpoint_id": 2,
                "in_clusters": [4, 5, 6, 16],
                "out_clusters": [],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_relay_c2acn01_77665544_analog_input",
            "sensor.lumi_lumi_relay_c2acn01_77665544_electrical_measurement",
            "sensor.lumi_lumi_relay_c2acn01_77665544_power",
            "light.lumi_lumi_relay_c2acn01_77665544_on_off",
            "light.lumi_lumi_relay_c2acn01_77665544_on_off_2",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.relay.c2acn01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 18, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            "2": {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            "3": {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 12, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input",
            "sensor.lumi_lumi_remote_b186acn01_77665544_power",
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_2",
            "sensor.lumi_lumi_remote_b186acn01_77665544_multistate_input_3",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b186acn01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 18, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            "2": {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            "3": {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 12, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input",
            "sensor.lumi_lumi_remote_b286acn01_77665544_power",
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_2",
            "sensor.lumi_lumi_remote_b286acn01_77665544_multistate_input_3",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b286acn01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            "2": {
                "device_type": -1,
                "endpoint_id": 2,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "3": {
                "device_type": -1,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "4": {
                "device_type": -1,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "5": {
                "device_type": -1,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "6": {
                "device_type": -1,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
        },
        "entities": ["sensor.lumi_lumi_remote_b286opcn01_77665544_power"],
        "event_channels": [6, 8, 768],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b286opcn01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            "2": {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
            "3": {
                "device_type": -1,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "4": {
                "device_type": -1,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "5": {
                "device_type": -1,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
            "6": {
                "device_type": -1,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": -1,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b486opcn01_77665544_power",
            "switch.lumi_lumi_remote_b486opcn01_77665544_on_off",
        ],
        "event_channels": [6, 8, 768, 6],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b486opcn01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 261,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6, 8, 768],
                "profile_id": 260,
            },
            "2": {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
            "3": {
                "device_type": None,
                "endpoint_id": 3,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            "4": {
                "device_type": None,
                "endpoint_id": 4,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            "5": {
                "device_type": None,
                "endpoint_id": 5,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
            "6": {
                "device_type": None,
                "endpoint_id": 6,
                "in_clusters": [],
                "out_clusters": [],
                "profile_id": None,
            },
        },
        "entities": [
            "sensor.lumi_lumi_remote_b686opcn01_77665544_power",
            "switch.lumi_lumi_remote_b686opcn01_77665544_on_off",
        ],
        "event_channels": [6, 8, 768, 6],
        "manufacturer": "LUMI",
        "model": "lumi.remote.b686opcn01",
    },
    {
        "endpoints": {
            "8": {
                "device_type": 256,
                "endpoint_id": 8,
                "in_clusters": [0, 6, 11, 17],
                "out_clusters": [0, 6],
                "profile_id": 260,
            }
        },
        "entities": ["light.lumi_lumi_router_77665544_on_off_on_off"],
        "event_channels": [6],
        "manufacturer": "LUMI",
        "model": "lumi.router",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 28417,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25],
                "out_clusters": [0, 3, 4, 5, 18, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 28418,
                "endpoint_id": 2,
                "in_clusters": [3, 18],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            "3": {
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
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_cube.aqgl01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 24322,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 1026, 1029, 65535],
                "out_clusters": [0, 3, 4, 5, 18, 25, 65535],
                "profile_id": 260,
            },
            "2": {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
            "3": {
                "device_type": 24323,
                "endpoint_id": 3,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 12],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.lumi_lumi_sensor_ht_77665544_power",
            "sensor.lumi_lumi_sensor_ht_77665544_temperature",
            "sensor.lumi_lumi_sensor_ht_77665544_humidity",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_ht",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2128,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 65535],
                "out_clusters": [0, 3, 4, 5, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.lumi_lumi_sensor_magnet_77665544_power",
            "binary_sensor.lumi_lumi_sensor_magnet_77665544_on_off",
        ],
        "event_channels": [6, 8],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_magnet",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [6],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_magnet.aq2",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 263,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1024, 1030, 1280, 65535],
                "out_clusters": [0, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_occupancy",
            "binary_sensor.lumi_lumi_sensor_motion_aq2_77665544_ias_zone",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_illuminance",
            "sensor.lumi_lumi_sensor_motion_aq2_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_motion.aq2",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 6,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3],
                "out_clusters": [0, 4, 5, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lumi_lumi_sensor_switch_77665544_power"],
        "event_channels": [6, 8],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 6,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 65535],
                "out_clusters": [0, 4, 6, 65535],
                "profile_id": 260,
            }
        },
        "entities": ["sensor.lumi_lumi_sensor_switch_aq2_77665544_power"],
        "event_channels": [6],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch.aq2",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [6],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_switch.aq3",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.sensor_wleak.aq1",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 10,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 25, 257, 1280],
                "out_clusters": [0, 3, 4, 5, 25],
                "profile_id": 260,
            },
            "2": {
                "device_type": 24322,
                "endpoint_id": 2,
                "in_clusters": [3],
                "out_clusters": [3, 4, 5, 18],
                "profile_id": 260,
            },
        },
        "entities": [
            "binary_sensor.lumi_lumi_vibration_aq1_77665544_ias_zone",
            "sensor.lumi_lumi_vibration_aq1_77665544_power",
            "lock.lumi_lumi_vibration_aq1_77665544_door_lock",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.vibration.aq1",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 24321,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 1026, 1027, 1029, 65535],
                "out_clusters": [0, 4, 65535],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.lumi_lumi_weather_77665544_temperature",
            "sensor.lumi_lumi_weather_77665544_power",
            "sensor.lumi_lumi_weather_77665544_humidity",
            "sensor.lumi_lumi_weather_77665544_pressure",
        ],
        "event_channels": [],
        "manufacturer": "LUMI",
        "model": "lumi.weather",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "NYCE",
        "model": "3010",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "NYCE",
        "model": "3014",
    },
    {
        "endpoints": {
            "3": {
                "device_type": 258,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 64527],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": ["light.osram_lightify_a19_rgbw_77665544_level_light_color_on_off"],
        "event_channels": [],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY A19 RGBW",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 2821],
                "out_clusters": [3, 6, 8, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.osram_lightify_dimming_switch_77665544_on_off",
            "sensor.osram_lightify_dimming_switch_77665544_power",
        ],
        "event_channels": [6, 8],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY Dimming Switch",
    },
    {
        "endpoints": {
            "3": {
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
        "event_channels": [],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY Flex RGBW",
    },
    {
        "endpoints": {
            "3": {
                "device_type": 258,
                "endpoint_id": 3,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2820, 64527],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.osram_lightify_rt_tunable_white_77665544_electrical_measurement",
            "light.osram_lightify_rt_tunable_white_77665544_level_light_color_on_off",
        ],
        "event_channels": [],
        "manufacturer": "OSRAM",
        "model": "LIGHTIFY RT Tunable White",
    },
    {
        "endpoints": {
            "3": {
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
        "event_channels": [],
        "manufacturer": "OSRAM",
        "model": "Plug 01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2064,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 32, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 25, 768, 4096],
                "profile_id": 260,
            },
            "2": {
                "device_type": 2064,
                "endpoint_id": 2,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            "3": {
                "device_type": 2064,
                "endpoint_id": 3,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            "4": {
                "device_type": 2064,
                "endpoint_id": 4,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            "5": {
                "device_type": 2064,
                "endpoint_id": 5,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
            "6": {
                "device_type": 2064,
                "endpoint_id": 6,
                "in_clusters": [0, 4096, 64768],
                "out_clusters": [3, 4, 5, 6, 8, 768, 4096],
                "profile_id": 260,
            },
        },
        "entities": ["sensor.osram_switch_4x_lightify_77665544_power"],
        "event_channels": [
            6,
            8,
            768,
            6,
            8,
            768,
            6,
            8,
            768,
            6,
            8,
            768,
            6,
            8,
            768,
            6,
            8,
            768,
        ],
        "manufacturer": "OSRAM",
        "model": "Switch 4x-LIGHTIFY",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2096,
                "endpoint_id": 1,
                "in_clusters": [0],
                "out_clusters": [0, 3, 4, 5, 6, 8],
                "profile_id": 49246,
            },
            "2": {
                "device_type": 12,
                "endpoint_id": 2,
                "in_clusters": [0, 1, 3, 15, 64512],
                "out_clusters": [25],
                "profile_id": 260,
            },
        },
        "entities": ["sensor.philips_rwl020_77665544_power"],
        "event_channels": [6, 8],
        "manufacturer": "Philips",
        "model": "RWL020",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.samjin_button_77665544_ias_zone",
            "sensor.samjin_button_77665544_temperature",
            "sensor.samjin_button_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "Samjin",
        "model": "button",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 64514],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.samjin_multi_77665544_power",
            "sensor.samjin_multi_77665544_temperature",
            "binary_sensor.samjin_multi_77665544_ias_zone",
            "binary_sensor.samjin_multi_77665544_manufacturer_specific",
        ],
        "event_channels": [],
        "manufacturer": "Samjin",
        "model": "multi",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "Samjin",
        "model": "water",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 0,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 6, 2820, 2821],
                "out_clusters": [0, 1, 3, 4, 5, 6, 25, 2820, 2821],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.securifi_ltd_unk_model_77665544_on_off",
            "sensor.securifi_ltd_unk_model_77665544_electrical_measurement",
            "sensor.securifi_ltd_unk_model_77665544_power",
            "switch.securifi_ltd_unk_model_77665544_on_off",
        ],
        "event_channels": [6],
        "manufacturer": "Securifi Ltd.",
        "model": None,
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-DWS04N_SF",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 256,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 4, 5, 6, 1794, 2820, 2821],
                "out_clusters": [3, 10, 25, 2821],
                "profile_id": 260,
            },
            "2": {
                "device_type": 259,
                "endpoint_id": 2,
                "in_clusters": [0, 1, 3],
                "out_clusters": [3, 6],
                "profile_id": 260,
            },
        },
        "entities": [
            "sensor.sercomm_corp_sz_esw01_77665544_smartenergy_metering",
            "sensor.sercomm_corp_sz_esw01_77665544_power",
            "sensor.sercomm_corp_sz_esw01_77665544_power_2",
            "sensor.sercomm_corp_sz_esw01_77665544_electrical_measurement",
            "switch.sercomm_corp_sz_esw01_77665544_on_off",
            "light.sercomm_corp_sz_esw01_77665544_on_off",
        ],
        "event_channels": [6],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-ESW01",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1024, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.sercomm_corp_sz_pir04_77665544_ias_zone",
            "sensor.sercomm_corp_sz_pir04_77665544_temperature",
            "sensor.sercomm_corp_sz_pir04_77665544_illuminance",
            "sensor.sercomm_corp_sz_pir04_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "Sercomm Corp.",
        "model": "SZ-PIR04",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "Sinope Technologies",
        "model": "RM3250ZB",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 769,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 513, 516, 1026, 2820, 2821, 65281],
                "out_clusters": [25, 65281],
                "profile_id": 260,
            },
            "196": {
                "device_type": 769,
                "endpoint_id": 196,
                "in_clusters": [1],
                "out_clusters": [],
                "profile_id": 49757,
            },
        },
        "entities": [
            "sensor.sinope_technologies_th1124zb_77665544_temperature",
            "sensor.sinope_technologies_th1124zb_77665544_power",
            "sensor.sinope_technologies_th1124zb_77665544_electrical_measurement",
        ],
        "event_channels": [],
        "manufacturer": "Sinope Technologies",
        "model": "TH1124ZB",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "SmartThings",
        "model": "outletv4",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 32768,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 15, 32],
                "out_clusters": [3, 25],
                "profile_id": 260,
            }
        },
        "entities": ["device_tracker.smartthings_tagv4_77665544_power"],
        "event_channels": [],
        "manufacturer": "SmartThings",
        "model": "tagv4",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 2,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 25],
                "out_clusters": [],
                "profile_id": 260,
            }
        },
        "entities": ["switch.third_reality_inc_3rss007z_77665544_on_off"],
        "event_channels": [],
        "manufacturer": "Third Reality, Inc",
        "model": "3RSS007Z",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "Third Reality, Inc",
        "model": "3RSS008Z",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 1026,
                "endpoint_id": 1,
                "in_clusters": [0, 1, 3, 32, 1026, 1280, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "binary_sensor.visonic_mct_340_e_77665544_ias_zone",
            "sensor.visonic_mct_340_e_77665544_temperature",
            "sensor.visonic_mct_340_e_77665544_power",
        ],
        "event_channels": [],
        "manufacturer": "Visonic",
        "model": "MCT-340 E",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "netvox",
        "model": "Z308E3ED",
    },
    {
        "endpoints": {
            "1": {
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
        "event_channels": [],
        "manufacturer": "sengled",
        "model": "E11-G13",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 1794, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.sengled_e12_n14_77665544_smartenergy_metering",
            "light.sengled_e12_n14_77665544_level_on_off",
        ],
        "event_channels": [],
        "manufacturer": "sengled",
        "model": "E12-N14",
    },
    {
        "endpoints": {
            "1": {
                "device_type": 257,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 1794, 2821],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "entities": [
            "sensor.sengled_z01_a19nae26_77665544_smartenergy_metering",
            "light.sengled_z01_a19nae26_77665544_level_light_color_on_off",
        ],
        "event_channels": [],
        "manufacturer": "sengled",
        "model": "Z01-A19NAE26",
    },
]
