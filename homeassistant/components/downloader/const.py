"""Constants for the Downloader component."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "downloader"
DEFAULT_NAME = "Downloader"
CONF_DOWNLOAD_DIR = "download_dir"

DOWNLOAD_FAILED_EVENT = "download_failed"
DOWNLOAD_COMPLETED_EVENT = "download_completed"
