"""Refoss data stored in the Home Assistant data object."""

from typing import NamedTuple

from refoss_ha.device_manager import RefossDeviceListener, RefossDeviceManager


class HomeAssistantRefossData(NamedTuple):
    """Refoss data stored in the Home Assistant data object."""

    device_manager: RefossDeviceManager
    device_listener: RefossDeviceListener
