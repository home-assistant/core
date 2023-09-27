"""Refoss data stored in the Home Assistant data object."""

from typing import NamedTuple

from refoss_ha.controller.device import BaseDevice


class HomeAssistantRefossData(NamedTuple):
    """Refoss data stored in the Home Assistant data object."""

    base_device: BaseDevice
