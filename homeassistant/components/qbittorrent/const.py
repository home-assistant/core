"""Added constants for the qbittorrent component."""

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

DEFAULT_NAME = "qbittorrent"
TRIM_SIZE = 35
CONF_CATEGORIES = "categories"

DOMAIN = DEFAULT_NAME

DATA_KEY_CLIENT = "client"
DATA_KEY_NAME = "name"

SERVICE_ADD_DOWNLOAD = "add_download"
SERVICE_REMOVE_DOWNLOAD = "remove_download"
