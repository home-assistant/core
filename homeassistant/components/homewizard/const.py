"""Constants for the Homewizard integration."""
from __future__ import annotations

from datetime import timedelta
from typing import TypedDict

# Set up.
from homewizard_energy.models import Data, Device, State

from homeassistant.const import Platform

DOMAIN = "homewizard"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

# Platform config.
CONF_API_ENABLED = "api_enabled"
CONF_DATA = "data"
CONF_DEVICE = "device"
CONF_PATH = "path"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_SERIAL = "serial"

UPDATE_INTERVAL = timedelta(seconds=5)


class DeviceResponseEntry(TypedDict):
    """Dict describing a single response entry."""

    device: Device
    data: Data
    state: State
