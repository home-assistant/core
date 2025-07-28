"""Constants for hello auth integration."""

import logging

DEFAULT_ACCESS = ["https://www.googleapis.com/auth/youtube.readonly"]
DOMAIN = "hinen"
MANUFACTURER = "hinen"
CHANNEL_CREATION_HELP_URL = "https://support.google.com/youtube/answer/1646861"

CONF_DEVICES = "devices"
CONF_UPLOAD_PLAYLIST = "upload_playlist_id"
COORDINATOR = "coordinator"
AUTH = "auth"
HOST = "host"
LOGGER = logging.getLogger(__package__)

ATTR_TITLE = "title"
ATTR_STATUS = "status"
ATTR_WORD_MODE = "VPPWorkMode"
ATTR_ALERT_STATUS = "alert_status"
ATTR_DEVICE_NAME = "device_name"
ATTR_TOTAL_VIEWS = "total_views"
ATTR_LATEST_VIDEO = "latest_video"
ATTR_SUBSCRIBER_COUNT = "subscriber_count"
ATTR_DESCRIPTION = "description"
ATTR_THUMBNAIL = "thumbnail"
ATTR_VIDEO_ID = "video_id"
ATTR_PUBLISHED_AT = "published_at"

# Work mode constants
WORK_MODE_NONE = 0
WORK_MODE_SELF_CONSUMPTION = 1
WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY = 2
WORK_MODE_SPECIFIED_POWER_CHARGE = 3
WORK_MODE_SPECIFIED_POWER_DISCHARGE = 4
WORK_MODE_BATTERY_IDLE = 5
WORK_MODE_CHARGE_DISCHARGE_TIME = 6

WORK_MODE_OPTIONS = {
    WORK_MODE_NONE: "none",
    WORK_MODE_SELF_CONSUMPTION: "Self-use",
    WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY: "Self-use(Generate only)",
    WORK_MODE_SPECIFIED_POWER_CHARGE: "Specified power charging",
    WORK_MODE_SPECIFIED_POWER_DISCHARGE: "Specified power discharge",
    WORK_MODE_BATTERY_IDLE: "Battery idle",
    WORK_MODE_CHARGE_DISCHARGE_TIME: "Charging and discharge time period",
}
