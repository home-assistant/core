"""Constants for the OpenDisplay integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from opendisplay import GlobalConfig

if TYPE_CHECKING:
    from opendisplay.models import FirmwareVersion

DOMAIN = "opendisplay"

STORAGE_DIR = "opendisplay"

# Brief delay after cancelling an in-flight BLE upload to let the device reset.
CANCEL_SETTLE_DELAY = 0.5


@dataclass
class OpenDisplayRuntimeData:
    """Runtime data for an OpenDisplay config entry."""

    firmware: FirmwareVersion
    device_config: GlobalConfig
