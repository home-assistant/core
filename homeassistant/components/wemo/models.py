"""Common data structures and helpers for accessing them."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pywemo

from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:  # Avoid circular dependencies.
    from . import HostPortTuple, WemoDiscovery, WemoDispatcher
    from .coordinator import DeviceCoordinator

DATA_WEMO: HassKey[WemoData] = HassKey(DOMAIN)


@dataclass
class WemoConfigEntryData:
    """Config entry state data."""

    device_coordinators: dict[str, DeviceCoordinator]
    discovery: WemoDiscovery
    dispatcher: WemoDispatcher


@dataclass
class WemoData:
    """Component state data."""

    discovery_enabled: bool
    static_config: Sequence[HostPortTuple]
    registry: pywemo.SubscriptionRegistry
    # config_entry_data is set when the config entry is loaded and unset when it's
    # unloaded. It's a programmer error if config_entry_data is accessed when the
    # config entry is not loaded
    config_entry_data: WemoConfigEntryData = None  # type: ignore[assignment]
