"""Common data structures and helpers for accessing them."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pywemo

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:  # Avoid circular dependencies.
    from . import HostPortTuple, WemoDiscovery, WemoDispatcher
    from .coordinator import DeviceCoordinator


@dataclass
class WemoConfigEntryData:
    """Config entry state data."""

    device_coordinators: dict[str, "DeviceCoordinator"]
    discovery: "WemoDiscovery"
    dispatcher: "WemoDispatcher"


@dataclass
class WemoData:
    """Component state data."""

    discovery_enabled: bool
    static_config: Sequence["HostPortTuple"]
    registry: pywemo.SubscriptionRegistry
    # config_entry_data is set when the config entry is loaded and unset when it's
    # unloaded. It's a programmer error if config_entry_data is accessed when the
    # config entry is not loaded
    config_entry_data: WemoConfigEntryData = None  # type: ignore[assignment]


@callback
def async_wemo_data(hass: HomeAssistant) -> WemoData:
    """Fetch WemoData with proper typing."""
    return cast(WemoData, hass.data[DOMAIN])
