"""Binary sensors derived from the Noonlight dispatch state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STATE_DISPATCHED, STATE_PENDING
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .entity import NoonlightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoonlightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Noonlight binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            NoonlightDispatchPending(coordinator),
            NoonlightDispatchActive(coordinator),
            NoonlightApiReachable(coordinator),
        ]
    )


class NoonlightDispatchPending(NoonlightEntity, BinarySensorEntity):
    """``on`` during the cancelable entry-delay grace window."""

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the dispatch pending binary sensor."""
        super().__init__(coordinator, "dispatch_pending")

    @property
    def is_on(self) -> bool:
        """Return True while the dispatch is in the pending grace window."""
        return self.coordinator.data["state"] == STATE_PENDING


class NoonlightDispatchActive(NoonlightEntity, BinarySensorEntity):
    """``on`` while a dispatch is live with Noonlight."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the dispatch active binary sensor."""
        super().__init__(coordinator, "dispatch_active")

    @property
    def is_on(self) -> bool:
        """Return True while a dispatch is live with Noonlight."""
        # SAFETY device class: ``on`` == unsafe == help is actively dispatched.
        return self.coordinator.data["state"] == STATE_DISPATCHED


class NoonlightApiReachable(NoonlightEntity, BinarySensorEntity):
    """``on`` while the idle heartbeat confirms Noonlight is reachable + authed.

    CONNECTIVITY device class: ``on`` == connected. Build automations on this
    to be warned of a broken token/network before you need to dispatch.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the API reachable binary sensor."""
        super().__init__(coordinator, "api_reachable")

    @property
    def is_on(self) -> bool:
        """Return True while the Noonlight API is reachable and authenticated."""
        # api_healthy is always present (set by _initial_state).
        return bool(self.coordinator.data["api_healthy"])
