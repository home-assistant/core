"""Constants for the Downloader component."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "downloader"
DEFAULT_NAME = "Downloader"
CONF_DOWNLOAD_DIR = "download_dir"
ATTR_DIGEST_AUTH = "digest_auth"
ATTR_FILENAME = "filename"
ATTR_DIGEST_PASSWORD = "digest_password"
ATTR_SUBDIR = "subdir"
ATTR_URL = "url"
ATTR_DIGEST_USERNAME = "digest_username"
ATTR_OVERWRITE = "overwrite"

CONF_DOWNLOAD_DIR = "download_dir"

DOWNLOAD_FAILED_EVENT = "download_failed"
DOWNLOAD_COMPLETED_EVENT = "download_completed"

SERVICE_DOWNLOAD_FILE = "download_file"
