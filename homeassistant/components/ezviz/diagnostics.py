"""Diagnostics support for EZVIZ."""

from typing import Any

from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import ATTR_TYPE_CLOUD
from .coordinator import EzvizConfigEntry

# Allowlist, as device data also contains raw API payloads with keys and addresses.
DEVICE_KEYS = (
    "version",
    "status",
    "device_category",
    "device_sub_category",
    "upgrade_available",
    "upgrade_in_progress",
    "upgrade_percent",
    "supportExt",
    "switches",
    "encrypted",
    "alarm_notify",
    "alarm_schedules_enabled",
    "alarm_sound_mod",
    "offline_notify",
    "push_notify_alarm",
    "push_notify_call",
    "local_rtsp_port",
    "supported_channels",
    "battery_level",
    "battery_camera_work_mode",
    "PIR_Status",
    "Motion_Trigger",
    "last_alarm_type_code",
    "last_alarm_type_name",
    "alarm_light_luminance",
    "Alarm_DetectHumanCar",
    "Alarm_AdvancedDetect",
    "NightVision_Model",
    "diskCapacity",
    "cam_timezone",
    "productId",
    "is_on",
    "brightness",
    "color_temperature",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EzvizConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "type": entry.data[CONF_TYPE],
        "options": {
            key: value
            for key, value in entry.options.items()
            if key in ("ffmpeg_arguments", "timeout")
        },
    }
    # Camera entries only hold RTSP credentials and have no coordinator.
    if entry.data[CONF_TYPE] == ATTR_TYPE_CLOUD:
        diagnostics["devices"] = [
            {key: device[key] for key in DEVICE_KEYS if key in device}
            for device in entry.runtime_data.data.values()
        ]
    return diagnostics
