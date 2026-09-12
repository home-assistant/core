"""Base entity classes for ADAM Audio.

Two flavours:
  AdamAudioEntity      - CoordinatorEntity bound to a single physical device.
  AdamAudioGroupEntity - Plain Entity that fans commands out to ALL devices
                         registered at call-time.  It self-subscribes to every
                         coordinator's update bus so the group state stays fresh.
"""

import asyncio
from typing import Any, override

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinators
from .const import DOMAIN, GROUP_DEVICE_ID, GROUP_DEVICE_NAME, MANUFACTURER
from .coordinator import AdamAudioCoordinator


class AdamAudioEntity(CoordinatorEntity[AdamAudioCoordinator]):
    """Base entity for a single physical speaker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info

    @property
    @override
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
        self._removed = False

    # ── Device info ──────────────────────────────────────────────────────────

    @property
    @override
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

    async def _async_call_all(self, method_name: str, *args: Any) -> None:
        """Run a client command on every speaker, then refresh all entities.

        All speakers are commanded concurrently.  The speakers that did apply
        the change are refreshed so the UI reflects them; a HomeAssistantError
        is then raised to surface the failure(s) to the user.

        Speakers whose command failed are deliberately *not* notified:
        async_set_updated_data() would mark their coordinator as having
        updated successfully (clearing UpdateFailed) and push their next poll
        a full interval into the future, hiding the failure.
        """
        coordinators = self._coordinators()
        results = await asyncio.gather(
            *(getattr(c.client, method_name)(*args) for c in coordinators),
            return_exceptions=True,
        )
        for coordinator, result in zip(coordinators, results, strict=True):
            if not isinstance(result, Exception):
                coordinator.async_notify_state()
        self.async_write_ha_state()

        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise HomeAssistantError(
                f"Command failed on {len(failures)} of {len(coordinators)} "
                f"speakers: {failures[0]}"
            )

    # ── HA lifecycle hooks ───────────────────────────────────────────────────

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to all coordinators so the group state stays live."""
        self._removed = False
        self._subscribe_coordinators()

    def _subscribe_coordinators(self) -> None:
        """(Re-)subscribe to update events from every known coordinator."""
        if self._removed:
            return
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
    @override
    def _async_write_ha_state(self) -> None:
        """Re-subscribe if new coordinators were added since last subscription."""
        if self._removed:
            return
        current_count = len(self._coordinators())
        if current_count != self._subscribed_count:
            self._subscribe_coordinators()
        super()._async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up coordinator listeners.

        Marks the entity removed first so any in-flight _async_call_all (e.g.
        awaiting asyncio.gather when a reload tears this entity down) that
        later calls async_write_ha_state() won't try to re-subscribe and
        double-unsub listeners we're about to remove here.
        """
        self._removed = True
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        self._subscribed_count = 0

    @property
    @override
    def available(self) -> bool:
        """Group is available if at least one device is online."""
        return any(c.client.available for c in self._coordinators())
