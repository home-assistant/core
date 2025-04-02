"""Support for SLZB-06 switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pysmlight import Sensors, SettingsEvent
from pysmlight.const import Settings

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
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
        entity_registry_enabled_default=False,
        state_fn=lambda x: x.auto_zigbee,
    ),
    SmSwitchEntityDescription(
        key="vpn_enabled",
        translation_key="vpn_enabled",
        setting=Settings.ENABLE_VPN,
        entity_registry_enabled_default=False,
        state_fn=lambda x: x.vpn_enabled,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize switches for SLZB-06 device."""
    coordinator = entry.runtime_data.data

    async_add_entities(SmSwitch(coordinator, switch) for switch in SWITCHES)


class SmSwitch(SmEntity, SwitchEntity):
    """Representation of a SLZB-06 switch."""

    coordinator: SmDataUpdateCoordinator
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

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.sse.register_settings_cb(
                self.entity_description.setting, self.event_callback
            )
        )

    async def set_smlight(self, state: bool) -> None:
        """Set the state on SLZB device."""
        await self.coordinator.client.set_toggle(self._page, self._toggle, state)

    @callback
    def event_callback(self, event: SettingsEvent) -> None:
        """Handle switch events from the SLZB device."""
        if event.setting is not None:
            self.coordinator.update_setting(
                self.entity_description.setting, event.setting[self._toggle]
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.set_smlight(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.set_smlight(False)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.state_fn(self.coordinator.data.sensors)
