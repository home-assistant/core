"""Constants for the Google Drive integration."""

from __future__ import annotations

DOMAIN = "google_drive"

DEFAULT_NAME = "Google Drive"
DRIVE_API_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_FOLDER_URL_PREFIX = "https://drive.google.com/drive/folders/"
OAUTH2_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]
