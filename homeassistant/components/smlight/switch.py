"""Support for SLZB-06 switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pysmlight import Sensors
from pysmlight.const import Settings

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmConfigEntry
from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmSwitchEntityDescription(SwitchEntityDescription):
    """Class to describe a Switch entity."""

    setting: Settings
    state_fn: Callable[[Sensors], bool | None]


SWITCHES: list[SmSwitchEntityDescription] = [
    SmSwitchEntityDescription(
        key="disable_led",
        translation_key="disable_led",
        setting=Settings.DISABLE_LEDS,
        state_fn=lambda x: x.disable_leds,
    ),
    SmSwitchEntityDescription(
        key="night_mode",
        translation_key="night_mode",
        setting=Settings.NIGHT_MODE,
        state_fn=lambda x: x.night_mode,
    ),
    SmSwitchEntityDescription(
        key="auto_zigbee_update",
        translation_key="auto_zigbee_update",
        entity_category=EntityCategory.CONFIG,
        setting=Settings.ZB_AUTOUPDATE,
        state_fn=lambda x: x.auto_zigbee,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize switches for SLZB-06 device."""
    coordinator = entry.runtime_data

    async_add_entities(SmSwitch(coordinator, switch) for switch in SWITCHES)


class SmSwitch(SmEntity, SwitchEntity):
    """Representation of a SLZB-06 switch."""

    entity_description: SmSwitchEntityDescription
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"

        self._page, self._toggle = description.setting.value

    async def set_smlight(self, state: bool) -> None:
        """Set the state on SLZB device."""
        await self.coordinator.client.set_toggle(self._page, self._toggle, state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.async_write_ha_state()

        await self.set_smlight(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._attr_is_on = False
        self.async_write_ha_state()

        await self.set_smlight(False)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.state_fn(self.coordinator.data.sensors)
