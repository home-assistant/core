"""Constants for the Google Drive integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "google_drive"

SCAN_INTERVAL = timedelta(hours=6)
DRIVE_FOLDER_URL_PREFIX = "https://drive.google.com/drive/folders/"
