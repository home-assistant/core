"""Added constants for the qbittorrent component."""

from datetime import timedelta

from homeassistant.core import DOMAIN

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_TOTAL_TORRENTS = "total_torrents"
SENSOR_TYPE_ACTIVE_TORRENTS = "active_torrents"
SENSOR_TYPE_INACTIVE_TORRENTS = "inactive_torrents"
SENSOR_TYPE_DOWNLOADING_TORRENTS = "downloading_torrents"
SENSOR_TYPE_SEEDING_TORRENTS = "seeding_torrents"
SENSOR_TYPE_RESUMED_TORRENTS = "resumed_torrents"
SENSOR_TYPE_PAUSED_TORRENTS = "paused_torrents"
SENSOR_TYPE_COMPLETED_TORRENTS = "completed_torrents"

DEFAULT_NAME = "qBittorrent"
TRIM_SIZE = 35
CONF_CATEGORIES = "categories"

SCAN_INTERVAL = timedelta(minutes=1)
DOMAIN = DEFAULT_NAME
