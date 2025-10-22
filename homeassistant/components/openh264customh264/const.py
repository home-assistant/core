"""Constants for the OpenH264 Nedis Camera integration."""
from __future__ import annotations
import logging

DOMAIN = "openh264customh264"
LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
CONF_MODE = "mode"
MODE_CAMERA = "camera_entity"
MODE_URL = "stream_url"

CONF_ENTITY_ID = "entity_id"
CONF_STREAM_URL = "stream_url"
CONF_SNAPSHOT_URL = "snapshot_url"

CONF_LIB_PATH = "lib_path"
CONF_ACCEPT_LICENSE = "accept_cisco_license"

DEFAULT_NAME = "OpenH264 Nedis Camera"
DEFAULT_TIMEOUT = 10
