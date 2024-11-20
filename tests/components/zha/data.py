"""Test data for ZHA API tests."""

BASE_CUSTOM_CONFIGURATION = {
    "schemas": {
        "zha_options": [
            {
                "type": "float",
                "valueMin": 0,
                "valueMax": 6553.6,
                "name": "default_light_transition",
                "optional": True,
                "default": 0,
            },
            {
                "type": "boolean",
                "name": "enhanced_light_transition",
                "required": True,
                "default": False,
            },
            {
                "type": "boolean",
                "name": "light_transitioning_flag",
                "required": True,
                "default": True,
            },
            {
                "type": "boolean",
                "name": "group_members_assume_state",
                "required": True,
                "default": True,
            },
            {
                "type": "boolean",
                "name": "enable_identify_on_join",
                "required": True,
                "default": True,
            },
            {
                "type": "integer",
                "valueMin": 0,
                "name": "consider_unavailable_mains",
                "optional": True,
                "default": 7200,
            },
            {
                "type": "integer",
                "valueMin": 0,
                "name": "consider_unavailable_battery",
                "optional": True,
                "default": 21600,
            },
            {
                "default": True,
                "name": "enable_mains_startup_polling",
                "required": True,
                "type": "boolean",
            },
        ]
    },
    "data": {
        "zha_options": {
            "enhanced_light_transition": True,
            "default_light_transition": 0,
            "light_transitioning_flag": True,
            "group_members_assume_state": False,
            "enable_identify_on_join": True,
            "enable_mains_startup_polling": True,
            "consider_unavailable_mains": 7200,
            "consider_unavailable_battery": 21600,
        }
    },
}

CONFIG_WITH_ALARM_OPTIONS = {
    "schemas": {
        "zha_options": [
            {
                "type": "float",
                "valueMin": 0,
                "valueMax": 6553.6,
                "name": "default_light_transition",
                "optional": True,
                "default": 0,
            },
            {
                "type": "boolean",
                "name": "enhanced_light_transition",
                "required": True,
                "default": False,
            },
            {
                "type": "boolean",
                "name": "light_transitioning_flag",
                "required": True,
                "default": True,
            },
            {
                "type": "boolean",
                "name": "group_members_assume_state",
                "required": True,
                "default": True,
            },
            {
                "type": "boolean",
                "name": "enable_identify_on_join",
                "required": True,
                "default": True,
            },
            {
                "type": "integer",
                "valueMin": 0,
                "name": "consider_unavailable_mains",
                "optional": True,
                "default": 7200,
            },
            {
                "type": "integer",
                "valueMin": 0,
                "name": "consider_unavailable_battery",
                "optional": True,
                "default": 21600,
            },
            {
                "default": True,
                "name": "enable_mains_startup_polling",
                "required": True,
                "type": "boolean",
            },
        ],
        "zha_alarm_options": [
            {
                "type": "string",
                "name": "alarm_master_code",
                "required": True,
                "default": "1234",
            },
            {
                "type": "integer",
                "valueMin": 0,
                "name": "alarm_failed_tries",
                "required": True,
                "default": 3,
            },
            {
                "type": "boolean",
                "name": "alarm_arm_requires_code",
                "required": True,
                "default": False,
            },
        ],
    },
    "data": {
        "zha_options": {
            "enhanced_light_transition": True,
            "default_light_transition": 0,
            "light_transitioning_flag": True,
            "group_members_assume_state": False,
            "enable_identify_on_join": True,
            "enable_mains_startup_polling": True,
            "consider_unavailable_mains": 7200,
            "consider_unavailable_battery": 21600,
        },
        "zha_alarm_options": {
            "alarm_arm_requires_code": False,
            "alarm_master_code": "4321",
            "alarm_failed_tries": 2,
        },
    },
}
