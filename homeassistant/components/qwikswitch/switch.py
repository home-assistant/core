"""Support for Qwikswitch relays."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN
from .entity import QSToggleEntity


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Add switches from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[DOMAIN]
    devs = [QSSwitch(qsid, qsusb) for qsid in discovery_info[DOMAIN]]
    add_entities(devs)


class QSSwitch(QSToggleEntity, SwitchEntity):
    """Switch based on a Qwikswitch relay module."""
