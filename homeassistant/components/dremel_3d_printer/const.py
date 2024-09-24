"""Constants for the Dremel 3D Printer (3D20, 3D40, 3D45) integration."""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__package__)

CAMERA_MODEL = "3D45"

DOMAIN = "dremel_3d_printer"

ATTR_EXTRUDER = "extruder"
ATTR_PLATFORM = "platform"
