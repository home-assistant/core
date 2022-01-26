"""Constants for the Homewizard integration."""
from __future__ import annotations

from datetime import timedelta
from typing import TypedDict

# Set up.
from aiohwenergy.device import Device

from homeassistant.const import Platform
from homeassistant.helpers.typing import StateType

DOMAIN = "homewizard"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

# Platform config.
CONF_SERIAL = "serial"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_DEVICE = "device"
CONF_DATA = "data"

UPDATE_INTERVAL = timedelta(seconds=5)


class DeviceResponseEntry(TypedDict):
    """Dict describing a single response entry."""

    device: Device
    data: dict[str, StateType]
