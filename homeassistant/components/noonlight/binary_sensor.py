"""Binary sensors derived from the Noonlight dispatch state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATE_DISPATCHED, STATE_PENDING
from .coordinator import NoonlightCoordinator
from .entity import NoonlightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Noonlight binary sensors."""
    coordinator: NoonlightCoordinator = hass.data[DOMAIN][entry.entry_id]
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
        super().__init__(coordinator, "dispatch_pending")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["state"] == STATE_PENDING


class NoonlightDispatchActive(NoonlightEntity, BinarySensorEntity):
    """``on`` while a dispatch is live with Noonlight."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        super().__init__(coordinator, "dispatch_active")

    @property
    def is_on(self) -> bool:
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
        super().__init__(coordinator, "api_reachable")

    @property
    def is_on(self) -> bool:
        # api_healthy is always present (set by _initial_state).
        return bool(self.coordinator.data["api_healthy"])
