"""Support for monitoring the qBittorrent API."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qbittorrent import Client

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import QBittorrentDataCoordinator


@dataclass(frozen=True, kw_only=True)
class QBittorrentSwitchEntityDescription(SwitchEntityDescription):
    """Describes qBittorren binary sensor entity."""

    update_fn: Callable[["QBittorrentSwitch"], bool]
    turn_on_fn: Callable[["QBittorrentSwitch"], None]
    turn_off_fn: Callable[["QBittorrentSwitch"], None]


def alternative_speed_turn_on(entity: "QBittorrentSwitch"):
    """Turn on alternative speed.

    qBittorrent only exposes the toggle for alternative speed, so we test if alternative_speed is false before using toggle.
    """

    if not entity.is_on:
        entity.client.toggle_alternative_speed()


def alternative_speed_turn_off(entity: "QBittorrentSwitch"):
    """Turn off alternative speed."""

    if entity.is_on:
        entity.client.toggle_alternative_speed()


SWITCH_TYPES: tuple[QBittorrentSwitchEntityDescription, ...] = (
    QBittorrentSwitchEntityDescription(
        key="alternative_speed",
        translation_key="alternative_speed",
        icon="mdi:speedometer-slow",
        update_fn=lambda entity: bool(entity.client.get_alternative_speed_status()),
        turn_on_fn=alternative_speed_turn_on,
        turn_off_fn=alternative_speed_turn_off,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""

    coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        QBittorrentSwitch(hass, coordinator.client, config_entry, description)
        for description in SWITCH_TYPES
    )


class QBittorrentSwitch(SwitchEntity):
    """Representation of a qBittorrent switch."""

    _attr_has_entity_name = True
    entity_description: QBittorrentSwitchEntityDescription
    client: Client

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        config_entry: ConfigEntry,
        entity_description: QBittorrentSwitchEntityDescription,
    ) -> None:
        """Initialize qBittorrent switch."""
        super().__init__()
        self.entity_description = entity_description
        self._attr_unique_id = f"{config_entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="QBittorrent",
        )
        self.client = client

    async def async_update(self) -> None:
        """Update entity value."""

        self._attr_is_on = await self.hass.async_add_executor_job(
            self.entity_description.update_fn, self
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this switch."""
        await self.hass.async_add_executor_job(self.entity_description.turn_on_fn, self)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this switch."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_off_fn, self
        )
