"""Constants for action/service checkers."""

from pylint_home_assistant.const import Platform

# Entity action methods per platform that serve as service/action handlers.
# These are the methods integration developers override on their entity
# subclasses. The HA framework calls these when a user triggers an action.
PLATFORM_ACTION_METHODS: dict[str, set[str]] = {
    Platform.ALARM_CONTROL_PANEL: {
        "async_alarm_arm_away",
        "async_alarm_arm_custom_bypass",
        "async_alarm_arm_home",
        "async_alarm_arm_night",
        "async_alarm_arm_vacation",
        "async_alarm_disarm",
        "async_alarm_trigger",
    },
    Platform.BUTTON: {
        "async_press",
    },
    Platform.CAMERA: {
        "async_disable_motion_detection",
        "async_enable_motion_detection",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.CLIMATE: {
        "async_set_fan_mode",
        "async_set_humidity",
        "async_set_hvac_mode",
        "async_set_preset_mode",
        "async_set_swing_horizontal_mode",
        "async_set_swing_mode",
        "async_set_temperature",
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.COVER: {
        "async_close_cover",
        "async_close_cover_tilt",
        "async_open_cover",
        "async_open_cover_tilt",
        "async_set_cover_position",
        "async_set_cover_tilt_position",
        "async_stop_cover",
        "async_stop_cover_tilt",
        "async_toggle",
        "async_toggle_tilt",
    },
    Platform.DATE: {
        "async_set_value",
    },
    Platform.DATETIME: {
        "async_set_value",
    },
    Platform.FAN: {
        "async_decrease_speed",
        "async_increase_speed",
        "async_oscillate",
        "async_set_direction",
        "async_set_percentage",
        "async_set_preset_mode",
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.HUMIDIFIER: {
        "async_set_humidity",
        "async_set_mode",
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.LAWN_MOWER: {
        "async_dock",
        "async_pause",
        "async_start_mowing",
    },
    Platform.LIGHT: {
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.LOCK: {
        "async_lock",
        "async_open",
        "async_unlock",
    },
    Platform.MEDIA_PLAYER: {
        "async_clear_playlist",
        "async_join_players",
        "async_media_next_track",
        "async_media_pause",
        "async_media_play",
        "async_media_play_pause",
        "async_media_previous_track",
        "async_media_seek",
        "async_media_stop",
        "async_mute_volume",
        "async_play_media",
        "async_select_sound_mode",
        "async_select_source",
        "async_set_repeat",
        "async_set_shuffle",
        "async_set_volume_level",
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
        "async_unjoin_player",
        "async_volume_down",
        "async_volume_up",
    },
    Platform.NOTIFY: {
        "async_send_message",
    },
    Platform.NUMBER: {
        "async_set_native_value",
    },
    Platform.REMOTE: {
        "async_delete_command",
        "async_learn_command",
        "async_send_command",
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.SCENE: {
        "async_activate",
    },
    Platform.SELECT: {
        "async_select_option",
    },
    Platform.SIREN: {
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.SWITCH: {
        "async_toggle",
        "async_turn_off",
        "async_turn_on",
    },
    Platform.TEXT: {
        "async_set_value",
    },
    Platform.TIME: {
        "async_set_value",
    },
    Platform.TODO: {
        "async_create_todo_item",
        "async_delete_todo_items",
        "async_move_todo_item",
        "async_update_todo_item",
    },
    Platform.UPDATE: {
        "async_clear_skipped",
        "async_install",
        "async_skip",
    },
    Platform.VACUUM: {
        "async_clean_spot",
        "async_locate",
        "async_pause",
        "async_return_to_base",
        "async_send_command",
        "async_set_fan_speed",
        "async_start",
        "async_stop",
    },
    Platform.VALVE: {
        "async_close_valve",
        "async_open_valve",
        "async_set_valve_position",
        "async_stop_valve",
        "async_toggle",
    },
    Platform.WATER_HEATER: {
        "async_set_operation_mode",
        "async_set_temperature",
        "async_turn_off",
        "async_turn_on",
    },
}
