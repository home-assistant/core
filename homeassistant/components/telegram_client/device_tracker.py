"""Tracks devices by sending a ICMP echo request (ping)."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .const import DOMAIN, SERVICE_EDIT_MESSAGE, SERVICE_SEND_MESSAGE
from .coordinator import TelegramClientCoordinator
from .entity import TelegramClientCoordinatorEntity
from .schemas import SERVICE_EDIT_MESSAGE_SCHEMA, SERVICE_SEND_MESSAGE_SCHEMA
from .services import async_telegram_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client device tracker entity."""
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_MESSAGE,
        SERVICE_SEND_MESSAGE_SCHEMA,
        "async_send_message",
    )
    platform.async_register_entity_service(
        SERVICE_EDIT_MESSAGE,
        SERVICE_EDIT_MESSAGE_SCHEMA,
        "async_edit_message",
    )
    if coordinator := hass.data[DOMAIN].get(entry.entry_id):
        async_add_entities(
            [
                TelegramClientDeviceTracker(
                    coordinator,
                    EntityDescription(
                        key="connected",
                        translation_key="connected",
                        name=coordinator.name,
                    ),
                )
            ]
        )


class TelegramClientDeviceTracker(TelegramClientCoordinatorEntity, ScannerEntity):
    """Representation of a Telegram client device tracker."""

    coordinator: TelegramClientCoordinator
    entity_description: EntityDescription

    @property
    def is_connected(self) -> bool:
        """Is connected."""
        return self.coordinator.client.is_connected()

    @property
    def source_type(self) -> SourceType:
        """Return the source type which is router."""
        return SourceType.ROUTER

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return self._attr_unique_id

    async def async_send_message(self, **kwargs) -> None:
        """Process Telegram send message service call."""
        await async_telegram_call(
            self.coordinator,
            SERVICE_SEND_MESSAGE,
            **kwargs,
        )

    async def async_edit_message(self, **kwargs) -> None:
        """Process Telegram edit message service call."""
        await async_telegram_call(
            self.coordinator,
            SERVICE_EDIT_MESSAGE,
            **kwargs,
        )
