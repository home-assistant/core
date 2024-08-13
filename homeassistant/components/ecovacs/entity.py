"""Ecovacs mqtt entity module."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import AvailabilityEvent
from deebot_client.events.base import Event
from sucks import EventListener, VacBot

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN

CapabilityEntity = TypeVar("CapabilityEntity")
EventT = TypeVar("EventT", bound=Event)


class EcovacsEntity(Entity, Generic[CapabilityEntity]):
    """Ecovacs entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _always_available: bool = False

    def __init__(
        self,
        device: Device,
        capability: CapabilityEntity,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        super().__init__(**kwargs)
        self._attr_unique_id = (
            f"{device.device_info['did']}_{self.entity_description.key}"
        )

        self._device = device
        self._capability = capability
        self._subscribed_events: set[type[Event]] = set()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        device_info = self._device.device_info
        info = DeviceInfo(
            identifiers={(DOMAIN, device_info["did"])},
            manufacturer="Ecovacs",
            sw_version=self._device.fw_version,
            serial_number=device_info["name"],
            model_id=device_info["class"],
        )

        if nick := device_info.get("nick"):
            info["name"] = nick

        if model := device_info.get("deviceName"):
            info["model"] = model

        if mac := self._device.mac:
            info["connections"] = {(dr.CONNECTION_NETWORK_MAC, mac)}

        return info

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        if not self._always_available:

            async def on_available(event: AvailabilityEvent) -> None:
                self._attr_available = event.available
                self.async_write_ha_state()

            self._subscribe(AvailabilityEvent, on_available)

    def _subscribe(
        self,
        event_type: type[EventT],
        callback: Callable[[EventT], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to events."""
        self._subscribed_events.add(event_type)
        self.async_on_remove(self._device.events.subscribe(event_type, callback))

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        for event_type in self._subscribed_events:
            self._device.events.request_refresh(event_type)


class EcovacsDescriptionEntity(EcovacsEntity[CapabilityEntity]):
    """Ecovacs entity."""

    def __init__(
        self,
        device: Device,
        capability: CapabilityEntity,
        entity_description: EntityDescription,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        super().__init__(device, capability, **kwargs)


@dataclass(kw_only=True, frozen=True)
class EcovacsCapabilityEntityDescription(
    EntityDescription,
    Generic[CapabilityEntity],
):
    """Ecovacs entity description."""

    capability_fn: Callable[[Capabilities], CapabilityEntity | None]


class EcovacsLegacyEntity(Entity):
    """Ecovacs legacy bot entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: VacBot) -> None:
        """Initialize the legacy Ecovacs entity."""
        self.device = device
        vacuum = device.vacuum

        self.error: str | None = None
        self._attr_unique_id = vacuum["did"]

        if (name := vacuum.get("nick")) is None:
            name = vacuum["did"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vacuum["did"])},
            manufacturer="Ecovacs",
            model=vacuum.get("deviceName"),
            name=name,
            serial_number=vacuum["did"],
        )

        self._event_listeners: list[EventListener] = []

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return super().available and self.state is not None

    async def async_will_remove_from_hass(self) -> None:
        """Remove event listeners on entity remove."""
        for listener in self._event_listeners:
            listener.unsubscribe()
