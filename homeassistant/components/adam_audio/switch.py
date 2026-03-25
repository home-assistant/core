"""Switch platform for ADAM Audio — Mute and Sleep.

Each physical speaker exposes two switches.  A single 'All Speakers' group
switch is also created the first time the platform is loaded; subsequent
config-entry loads skip it because the unique_id is already registered.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, ENTITY_MUTE, ENTITY_SLEEP, GROUP_DEVICE_ID
from .coordinator import AdamAudioCoordinator
from .entity import AdamAudioEntity, AdamAudioGroupEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import AdamAudioConfigEntry, AdamAudioIntegrationData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data.coordinator
    integration_data: AdamAudioIntegrationData = hass.data[DOMAIN]

    entities: list[SwitchEntity] = [
        AdamAudioSleepSwitch(coordinator),
        AdamAudioMuteSwitch(coordinator),
    ]

    # Create group entities exactly once per HA lifecycle.
    if not integration_data.group_switches_added:
        integration_data.group_switches_added = True
        entities += [
            AdamAudioGroupSleepSwitch(hass),
            AdamAudioGroupMuteSwitch(hass),
        ]

    async_add_entities(entities)


# ── Per-device switches ───────────────────────────────────────────────────────


class AdamAudioMuteSwitch(AdamAudioEntity, SwitchEntity):
    """Mute switch for a single speaker."""

    _attr_translation_key = "mute"
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the mute switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_unique_id}_{ENTITY_MUTE}"

    @property
    def is_on(self) -> bool:
        """Return true if muted."""
        return self.coordinator.client.state.mute

    @property
    def icon(self) -> str:
        """Return icon based on mute state."""
        return "mdi:volume-off" if self.is_on else "mdi:volume-high"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on mute."""
        await self.coordinator.client.async_set_mute(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off mute."""
        await self.coordinator.client.async_set_mute(False)
        self.async_write_ha_state()


class AdamAudioSleepSwitch(AdamAudioEntity, SwitchEntity):
    """Standby (sleep) switch for a single speaker."""

    _attr_translation_key = "sleep"
    _attr_icon = "mdi:power-sleep"

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the sleep switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_unique_id}_{ENTITY_SLEEP}"

    @property
    def is_on(self) -> bool:
        """Return true if sleeping."""
        return self.coordinator.client.state.sleep

    @property
    def icon(self) -> str:
        """Return icon based on sleep state."""
        return "mdi:power-sleep" if self.is_on else "mdi:power"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on sleep mode."""
        await self.coordinator.client.async_set_sleep(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off sleep mode."""
        await self.coordinator.client.async_set_sleep(False)
        self.async_write_ha_state()


# ── Group switches ────────────────────────────────────────────────────────────


class AdamAudioGroupMuteSwitch(AdamAudioGroupEntity, SwitchEntity):
    """Mute switch that controls ALL speakers simultaneously."""

    _attr_translation_key = "mute"
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_MUTE}"

    @property
    def icon(self) -> str:
        """Return icon based on mute state."""
        return "mdi:volume-off" if self.is_on else "mdi:volume-high"

    @property
    def is_on(self) -> bool:
        """Return true when ALL speakers are muted."""
        coordinators = self._coordinators()
        if not coordinators:
            return False
        return all(c.client.state.mute for c in coordinators)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute all speakers."""
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_mute(True) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute all speakers."""
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_mute(False) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()


class AdamAudioGroupSleepSwitch(AdamAudioGroupEntity, SwitchEntity):
    """Sleep switch that controls ALL speakers simultaneously."""

    _attr_translation_key = "sleep"
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_SLEEP}"

    @property
    def icon(self) -> str:
        """Return icon based on sleep state."""
        return "mdi:power-sleep" if self.is_on else "mdi:power"

    @property
    def is_on(self) -> bool:
        """Return true when ALL speakers are sleeping."""
        coordinators = self._coordinators()
        if not coordinators:
            return False
        return all(c.client.state.sleep for c in coordinators)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put all speakers to sleep."""
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_sleep(True) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Wake all speakers."""
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_sleep(False) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()
