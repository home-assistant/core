"""Switch platform for ADAM Audio — Mute and Sleep.

Each physical speaker exposes two switches.  A single 'All Speakers' group
switch is also created the first time the platform is loaded; subsequent
config-entry loads skip it because the unique_id is already registered.
"""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import get_integration_data
from .const import DOMAIN, ENTITY_MUTE, ENTITY_SLEEP, GROUP_DEVICE_ID
from .coordinator import AdamAudioCoordinator
from .data import AdamAudioConfigEntry
from .entity import AdamAudioEntity, AdamAudioGroupEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data.coordinator
    integration_data = get_integration_data(hass)

    entities: list[SwitchEntity] = [
        AdamAudioSleepSwitch(coordinator),
        AdamAudioMuteSwitch(coordinator),
    ]

    # Create group entities exactly once; the flags are reset when the owning
    # entry unloads so a reload recreates them.
    if not integration_data.group_switches_added:
        integration_data.group_switches_added = True
        integration_data.group_owner_entry_id = entry.entry_id
        entities += [
            AdamAudioGroupSleepSwitch(hass),
            AdamAudioGroupMuteSwitch(hass),
        ]

    async_add_entities(entities)


# ── Per-device switches ───────────────────────────────────────────────────────


class AdamAudioMuteSwitch(AdamAudioEntity, SwitchEntity):
    """Mute switch for a single speaker."""

    _attr_translation_key = "mute"

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the mute switch."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            # pylint: disable-next=home-assistant-entity-unique-id-redundant-domain
            f"{DOMAIN}_{coordinator.entity_unique_id_base}_{ENTITY_MUTE}"
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if muted."""
        return self.coordinator.client.state.mute

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on mute."""
        await self.coordinator.client.async_set_mute(True)
        self.coordinator.async_notify_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off mute."""
        await self.coordinator.client.async_set_mute(False)
        self.coordinator.async_notify_state()


class AdamAudioSleepSwitch(AdamAudioEntity, SwitchEntity):
    """Standby (sleep) switch for a single speaker."""

    _attr_translation_key = "sleep"

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the sleep switch."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            # pylint: disable-next=home-assistant-entity-unique-id-redundant-domain
            f"{DOMAIN}_{coordinator.entity_unique_id_base}_{ENTITY_SLEEP}"
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if sleeping."""
        return self.coordinator.client.state.sleep

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on sleep mode."""
        await self.coordinator.client.async_set_sleep(True)
        self.coordinator.async_notify_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off sleep mode."""
        await self.coordinator.client.async_set_sleep(False)
        self.coordinator.async_notify_state()


# ── Group switches ────────────────────────────────────────────────────────────


class AdamAudioGroupMuteSwitch(AdamAudioGroupEntity, SwitchEntity):
    """Mute switch that controls ALL speakers simultaneously."""

    _attr_translation_key = "mute"
    # pylint: disable-next=home-assistant-entity-unique-id-redundant-domain
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_MUTE}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true when ALL speakers are muted."""
        coordinators = self._coordinators()
        if not coordinators:
            return False
        return all(c.client.state.mute for c in coordinators)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute all speakers."""
        await self._async_call_all("async_set_mute", True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute all speakers."""
        await self._async_call_all("async_set_mute", False)


class AdamAudioGroupSleepSwitch(AdamAudioGroupEntity, SwitchEntity):
    """Sleep switch that controls ALL speakers simultaneously."""

    _attr_translation_key = "sleep"
    # pylint: disable-next=home-assistant-entity-unique-id-redundant-domain
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_SLEEP}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true when ALL speakers are sleeping."""
        coordinators = self._coordinators()
        if not coordinators:
            return False
        return all(c.client.state.sleep for c in coordinators)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put all speakers to sleep."""
        await self._async_call_all("async_set_sleep", True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Wake all speakers."""
        await self._async_call_all("async_set_sleep", False)
