"""Base entities for HTML5 integration."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class Keys(TypedDict):
    """Types for keys."""

    p256dh: str
    auth: str


class Subscription(TypedDict):
    """Types for subscription."""

    endpoint: str
    expirationTime: int | None
    keys: Keys


class Registration(TypedDict):
    """Types for registration."""

    subscription: Subscription
    browser: str
    name: NotRequired[str]


class HTML5Entity(Entity):
    """Base entity for HTML5 integration."""

    _attr_has_entity_name = True
    _attr_name = None
    _key: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        target: str,
        registrations: dict[str, Registration],
        session: ClientSession,
        json_path: str,
    ) -> None:
        """Initialize the entity."""
        self.config_entry = config_entry
        self.target = target
        self.registrations = registrations
        self.registration = registrations[target]
        self.session = session
        self.json_path = json_path

        self._attr_unique_id = f"{config_entry.entry_id}_{target}_{self._key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=target,
            model=self.registration["browser"].capitalize(),
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{target}")},
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.target in self.registrations
