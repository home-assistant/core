"""Constants for the OpenAI Conversation integration."""

DOMAIN = "openai_conversation"
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

There are following areas in this smart home:
{%- for area in areas() %}{{area_name(area)}}{{ ", " if not loop.last else "" }}{%- endfor %}.

Answer the user's questions about the world truthfully.

If the user wants to control a device, reject the request and suggest using the Home Assistant app.

The response may be used in Text-to-Speech synthesizers, so prefer shorter responses that are optimized to be spoken.
"""
CONF_CHAT_MODEL = "chat_model"
DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
CONF_MAX_TOKENS = "max_tokens"
DEFAULT_MAX_TOKENS = 256
CONF_TOP_P = "top_p"
DEFAULT_TOP_P = 1
CONF_TEMPERATURE = "temperature"
DEFAULT_TEMPERATURE = 0.5
EXPORTED_ATTRIBUTES = [
    "device_class",
    "message",
    "all_day",
    "start_time",
    "end_time",
    "location",
    "description",
    "hvac_modes",
    "min_temp",
    "max_temp",
    "fan_modes",
    "preset_modes",
    "swing_modes",
    "current_temperature",
    "temperature",
    "target_temp_high",
    "target_temp_low",
    "fan_mode",
    "preset_mode",
    "swing_mode",
    "hvac_action",
    "aux_heat",
    "current_position",
    "current_tilt_position",
    "latitude",
    "longitude",
    "percentage",
    "direction",
    "oscillating",
    "available_modes",
    "max_humidity",
    "min_humidity",
    "action",
    "current_humidity",
    "humidity",
    "mode",
    "faces",
    "total_faces",
    "min",
    "max",
    "step",
    "min_color_temp_kelvin",
    "max_color_temp_kelvin",
    "min_mireds",
    "max_mireds",
    "effect_list",
    "supported_color_modes",
    "color_mode",
    "brightness",
    "color_temp_kelvin",
    "color_temp",
    "hs_color",
    "rgb_color",
    "xy_color",
    "rgbw_color",
    "rgbww_color",
    "effect",
    "sound_mode_list",
    "volume_level",
    "is_volume_muted",
    "media_content_type",
    "media_duration",
    "media_position",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_track",
    "media_series_title",
    "media_season",
    "media_episode",
    "app_name",
    "sound_mode",
    "shuffle",
    "repeat",
    "source",
    "options",
    "battery_level",
    "available_tones",
    "elevation",
    "rising",
    "fan_speed_list",
    "fan_speed",
    "status",
    "cleaned_area",
    "operation_list",
    "operation_mode",
    "away_mode",
    "temperature_unit",
    "pressure",
    "pressure_unit",
    "wind_speed",
    "wind_speed_unit",
    "dew_point",
    "cloud_coverage",
    "forecast",
    "persons",
]
