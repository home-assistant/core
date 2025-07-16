"""Constants for the Downloader component."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "downloader"
DEFAULT_NAME = "Downloader"
ATTR_AUTH_PASSWORD = "auth_password"
ATTR_AUTH_TYPE = "auth_type"
ATTR_AUTH_USERNAME = "auth_username"
ATTR_FILENAME = "filename"
ATTR_OVERWRITE = "overwrite"
ATTR_SUBDIR = "subdir"
ATTR_URL = "url"

CONF_DOWNLOAD_DIR = "download_dir"

DOWNLOAD_FAILED_EVENT = "download_failed"
DOWNLOAD_COMPLETED_EVENT = "download_completed"

SERVICE_DOWNLOAD_FILE = "download_file"
