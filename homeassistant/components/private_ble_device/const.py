"""Constants for Private BLE Device."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .coordinator import PrivateDevicesCoordinator

DOMAIN = "private_ble_device"

# Resolving a private MAC against an IRK costs AES work, so a single
# coordinator does it once for every config entry rather than per entry.
COORDINATOR: HassKey[PrivateDevicesCoordinator] = HassKey(f"{DOMAIN}_coordinator")
