"""Constants for the Homewizard integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform

if TYPE_CHECKING:
    from homewizard_energy.models import Data, Device, State, System

DOMAIN = "homewizard"
PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

LOGGER = logging.getLogger(__package__)

# Platform config.
CONF_API_ENABLED = "api_enabled"
CONF_DATA = "data"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_SERIAL = "serial"

UPDATE_INTERVAL = timedelta(seconds=5)


@dataclass
class DeviceResponseEntry:
    """Dict describing a single response entry."""

    device: Device
    data: Data
    state: State | None = None
    system: System | None = None
