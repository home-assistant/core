"""Z-Wave discovery schemas."""
from . import const

DEFAULT_VALUES_SCHEMA = {
    "power": {
        const.DISC_SCHEMAS: [
            {
                const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SENSOR_MULTILEVEL],
                const.DISC_INDEX: [const.INDEX_SENSOR_MULTILEVEL_POWER],
            },
            {
                const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_METER],
                const.DISC_INDEX: [const.INDEX_METER_POWER],
            },
        ],
        const.DISC_OPTIONAL: True,
    }
}

DISCOVERY_SCHEMAS = [
    {
        const.DISC_COMPONENT: "binary_sensor",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_ENTRY_CONTROL,
            const.GENERIC_TYPE_SENSOR_ALARM,
            const.GENERIC_TYPE_SENSOR_BINARY,
            const.GENERIC_TYPE_SWITCH_BINARY,
            const.GENERIC_TYPE_METER,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_SENSOR_NOTIFICATION,
            const.GENERIC_TYPE_THERMOSTAT,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SENSOR_BINARY],
                    const.DISC_TYPE: const.TYPE_BOOL,
                    const.DISC_GENRE: const.GENRE_USER,
                },
                "off_delay": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_CONFIGURATION],
                    const.DISC_INDEX: [9],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "climate",  # thermostat without COMMAND_CLASS_THERMOSTAT_MODE
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_THERMOSTAT_HEATING,
            const.SPECIFIC_TYPE_SETPOINT_THERMOSTAT,
            const.SPECIFIC_TYPE_NOT_USED,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT]
                },
                "temperature": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SENSOR_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SENSOR_MULTILEVEL_TEMPERATURE],
                    const.DISC_OPTIONAL: True,
                },
                "fan_mode": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_FAN_MODE],
                    const.DISC_OPTIONAL: True,
                },
                "operating_state": {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_THERMOSTAT_OPERATING_STATE
                    ],
                    const.DISC_OPTIONAL: True,
                },
                "fan_action": {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_THERMOSTAT_FAN_ACTION
                    ],
                    const.DISC_OPTIONAL: True,
                },
                "mode": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_MODE],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "climate",  # thermostat with COMMAND_CLASS_THERMOSTAT_MODE
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_THERMOSTAT_GENERAL,
            const.SPECIFIC_TYPE_THERMOSTAT_GENERAL_V2,
            const.SPECIFIC_TYPE_SETBACK_THERMOSTAT,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_MODE]
                },
                "setpoint_heating": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [1],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_cooling": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [2],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_furnace": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [7],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_dry_air": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [8],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_moist_air": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [9],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_auto_changeover": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [10],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_eco_heating": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [11],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_eco_cooling": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [12],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_away_heating": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [13],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_away_cooling": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [14],
                    const.DISC_OPTIONAL: True,
                },
                "setpoint_full_power": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
                    const.DISC_INDEX: [15],
                    const.DISC_OPTIONAL: True,
                },
                "temperature": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SENSOR_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SENSOR_MULTILEVEL_TEMPERATURE],
                    const.DISC_OPTIONAL: True,
                },
                "fan_mode": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_THERMOSTAT_FAN_MODE],
                    const.DISC_OPTIONAL: True,
                },
                "operating_state": {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_THERMOSTAT_OPERATING_STATE
                    ],
                    const.DISC_OPTIONAL: True,
                },
                "fan_action": {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_THERMOSTAT_FAN_ACTION
                    ],
                    const.DISC_OPTIONAL: True,
                },
                "zxt_120_swing_mode": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_CONFIGURATION],
                    const.DISC_INDEX: [33],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "cover",  # Rollershutter
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_GENRE: const.GENRE_USER,
                },
                "open": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SWITCH_MULTILEVEL_BRIGHT],
                    const.DISC_OPTIONAL: True,
                },
                "close": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SWITCH_MULTILEVEL_DIM],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "cover",  # Garage Door Switch
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_BINARY],
                    const.DISC_GENRE: const.GENRE_USER,
                }
            },
        ),
    },
    {
        const.DISC_COMPONENT: "cover",  # Garage Door Barrier
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_BARRIER_OPERATOR],
                    const.DISC_INDEX: [const.INDEX_BARRIER_OPERATOR_LABEL],
                }
            },
        ),
    },
    {
        const.DISC_COMPONENT: "fan",
        const.DISC_GENERIC_DEVICE_CLASS: [const.GENERIC_TYPE_SWITCH_MULTILEVEL],
        const.DISC_SPECIFIC_DEVICE_CLASS: [const.SPECIFIC_TYPE_FAN_SWITCH],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SWITCH_MULTILEVEL_LEVEL],
                    const.DISC_TYPE: const.TYPE_BYTE,
                }
            },
        ),
    },
    {
        const.DISC_COMPONENT: "light",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_REMOTE,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
            const.SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
            const.SPECIFIC_TYPE_NOT_USED,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SWITCH_MULTILEVEL_LEVEL],
                    const.DISC_TYPE: const.TYPE_BYTE,
                },
                "dimming_duration": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
                    const.DISC_INDEX: [const.INDEX_SWITCH_MULTILEVEL_DURATION],
                    const.DISC_OPTIONAL: True,
                },
                "color": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_COLOR],
                    const.DISC_INDEX: [const.INDEX_SWITCH_COLOR_COLOR],
                    const.DISC_OPTIONAL: True,
                },
                "color_channels": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_COLOR],
                    const.DISC_INDEX: [const.INDEX_SWITCH_COLOR_CHANNELS],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "lock",
        const.DISC_GENERIC_DEVICE_CLASS: [const.GENERIC_TYPE_ENTRY_CONTROL],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_DOOR_LOCK,
            const.SPECIFIC_TYPE_ADVANCED_DOOR_LOCK,
            const.SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK,
            const.SPECIFIC_TYPE_SECURE_LOCKBOX,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_DOOR_LOCK],
                    const.DISC_INDEX: [const.INDEX_DOOR_LOCK_LOCK],
                },
                "access_control": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_ALARM],
                    const.DISC_INDEX: [const.INDEX_ALARM_ACCESS_CONTROL],
                    const.DISC_OPTIONAL: True,
                },
                "alarm_type": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_ALARM],
                    const.DISC_INDEX: [const.INDEX_ALARM_TYPE],
                    const.DISC_OPTIONAL: True,
                },
                "alarm_level": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_ALARM],
                    const.DISC_INDEX: [const.INDEX_ALARM_LEVEL],
                    const.DISC_OPTIONAL: True,
                },
                "v2btze_advanced": {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_CONFIGURATION],
                    const.DISC_INDEX: [12],
                    const.DISC_OPTIONAL: True,
                },
            },
        ),
    },
    {
        const.DISC_COMPONENT: "sensor",
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                        const.COMMAND_CLASS_METER,
                        const.COMMAND_CLASS_ALARM,
                        const.COMMAND_CLASS_SENSOR_ALARM,
                        const.COMMAND_CLASS_INDICATOR,
                        const.COMMAND_CLASS_BATTERY,
                    ],
                    const.DISC_GENRE: const.GENRE_USER,
                }
            },
        ),
    },
    {
        const.DISC_COMPONENT: "switch",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_METER,
            const.GENERIC_TYPE_SENSOR_ALARM,
            const.GENERIC_TYPE_SENSOR_BINARY,
            const.GENERIC_TYPE_SWITCH_BINARY,
            const.GENERIC_TYPE_ENTRY_CONTROL,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_SENSOR_NOTIFICATION,
            const.GENERIC_TYPE_GENERIC_CONTROLLER,
            const.GENERIC_TYPE_SWITCH_REMOTE,
            const.GENERIC_TYPE_REPEATER_SLAVE,
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_WALL_CONTROLLER,
        ],
        const.DISC_VALUES: dict(
            DEFAULT_VALUES_SCHEMA,
            **{
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [const.COMMAND_CLASS_SWITCH_BINARY],
                    const.DISC_TYPE: const.TYPE_BOOL,
                    const.DISC_GENRE: const.GENRE_USER,
                }
            },
        ),
    },
]
