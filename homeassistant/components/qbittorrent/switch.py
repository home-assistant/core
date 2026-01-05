"""Support for monitoring the qBittorrent API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QBittorrentDataCoordinator


@dataclass(frozen=True, kw_only=True)
class QBittorrentSwitchEntityDescription(SwitchEntityDescription):
    """Describes qBittorren switch."""

    is_on_func: Callable[[QBittorrentDataCoordinator], bool]
    turn_on_fn: Callable[[QBittorrentDataCoordinator], None]
    turn_off_fn: Callable[[QBittorrentDataCoordinator], None]
    toggle_func: Callable[[QBittorrentDataCoordinator], None]


SWITCH_TYPES: tuple[QBittorrentSwitchEntityDescription, ...] = (
    QBittorrentSwitchEntityDescription(
        key="alternative_speed",
        translation_key="alternative_speed",
        icon="mdi:speedometer-slow",
        is_on_func=lambda coordinator: coordinator.get_alt_speed_enabled(),
        turn_on_fn=lambda coordinator: coordinator.set_alt_speed_enabled(True),
        turn_off_fn=lambda coordinator: coordinator.set_alt_speed_enabled(False),
        toggle_func=lambda coordinator: coordinator.toggle_alt_speed_enabled(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up qBittorrent switch entries."""

    coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        QBittorrentSwitch(coordinator, config_entry, description)
        for description in SWITCH_TYPES
    )


class QBittorrentSwitch(CoordinatorEntity[QBittorrentDataCoordinator], SwitchEntity):
    """Representation of a qBittorrent switch."""

    _attr_has_entity_name = True
    entity_description: QBittorrentSwitchEntityDescription

    def __init__(
        self,
        coordinator: QBittorrentDataCoordinator,
        config_entry: ConfigEntry,
        entity_description: QBittorrentSwitchEntityDescription,
    ) -> None:
        """Initialize qBittorrent switch."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{config_entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="QBittorrent",
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_func(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this switch."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_on_fn, self.coordinator
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this switch."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_off_fn, self.coordinator
        )
        await self.coordinator.async_request_refresh()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the device."""
        await self.hass.async_add_executor_job(
            self.entity_description.toggle_func, self.coordinator
        )
        await self.coordinator.async_request_refresh()
