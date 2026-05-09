"""Base entity classes for ADAM Audio.

Two flavours:
  AdamAudioEntity      - CoordinatorEntity bound to a single physical device.
  AdamAudioGroupEntity - Plain Entity that fans commands out to ALL devices
                         registered at call-time.  It self-subscribes to every
                         coordinator's update bus so the group state stays fresh.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinators
from .const import DOMAIN, GROUP_DEVICE_ID, GROUP_DEVICE_NAME, MANUFACTURER
from .coordinator import AdamAudioCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class AdamAudioEntity(CoordinatorEntity[AdamAudioCoordinator]):
    """Base entity for a single physical speaker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Mark unavailable if the coordinator fails or the client drops."""
        return super().available and self.coordinator.client.available


class AdamAudioGroupEntity(Entity):
    """Base entity for the virtual 'All Speakers' device.

    Commands are dispatched concurrently to every real device coordinator.
    State is derived from the collective state of all coordinators.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the group entity."""
        self._hass = hass
        self._unsub_listeners: list = []
        self._subscribed_count: int = 0

    # ── Device info ──────────────────────────────────────────────────────────

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the 'All Speakers' group device."""
        return DeviceInfo(
            identifiers={(DOMAIN, GROUP_DEVICE_ID)},
            name=GROUP_DEVICE_NAME,
            manufacturer=MANUFACTURER,
            model="Group",
        )

    # ── Coordinator helpers ──────────────────────────────────────────────────

    def _coordinators(self) -> list[AdamAudioCoordinator]:
        """Return all currently loaded device coordinators."""
        return get_coordinators(self._hass)

    # ── HA lifecycle hooks ───────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        """Subscribe to all coordinators so the group state stays live."""
        self._subscribe_coordinators()

    def _subscribe_coordinators(self) -> None:
        """(Re-)subscribe to update events from every known coordinator."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

        @callback
        def _on_coordinator_update() -> None:
            self.async_write_ha_state()

        for coordinator in self._coordinators():
            self._unsub_listeners.append(
                coordinator.async_add_listener(_on_coordinator_update)
            )
        self._subscribed_count = len(self._unsub_listeners)

    @callback
    def async_write_ha_state(self) -> None:
        """Re-subscribe if new coordinators were added since last subscription."""
        current_count = len(self._coordinators())
        if current_count != self._subscribed_count:
            self._subscribe_coordinators()
        super().async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up coordinator listeners."""
        for unsub in self._unsub_listeners:
            unsub()

    @property
    def available(self) -> bool:
        """Group is available if at least one device is online."""
        return any(c.client.available for c in self._coordinators())
