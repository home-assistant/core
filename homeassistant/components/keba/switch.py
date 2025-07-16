"""Support for KEBA charging station switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, KebaHandler


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba: KebaHandler = hass.data[DOMAIN]

    switches = [KebaSwitchUser(keba, "Charging", "charging")]
    async_add_entities(switches)


class KebaSwitchUser(SwitchEntity):
    """The entity class for KEBA charging stations switch."""

    _attr_should_poll = False

    def __init__(self, keba: KebaHandler, name: str, entity_type: str) -> None:
        """Initialize the KEBA switch."""
        self._keba = keba
        self._attr_is_on = True
        self._attr_name = f"{keba.device_name} {name}"
        self._attr_unique_id = f"{keba.device_id}_{entity_type}"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Lock wallbox."""
        await self._keba.async_disable_ev()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Unlock wallbox."""
        await self._keba.async_enable_ev()

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the switch."""
        self._attr_is_on = self._keba.get_value("Enable user") == 1

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
