"""Remote control support for Bravia TV."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BraviaTVCoordinator
from .const import ATTR_MANUFACTURER, DEFAULT_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bravia TV Remote from a config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = config_entry.unique_id
    assert unique_id is not None
    device_info = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer=ATTR_MANUFACTURER,
        model=config_entry.title,
        name=DEFAULT_NAME,
    )

    async_add_entities(
        [BraviaTVRemote(coordinator, DEFAULT_NAME, unique_id, device_info)]
    )


class BraviaTVRemote(CoordinatorEntity[BraviaTVCoordinator], RemoteEntity):
    """Representation of a Bravia TV Remote."""

    def __init__(
        self,
        coordinator: BraviaTVCoordinator,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""

        self._attr_device_info = device_info
        self._attr_name = name
        self._attr_unique_id = unique_id

        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.async_turn_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to device."""
        repeats = kwargs[ATTR_NUM_REPEATS]
        await self.coordinator.async_send_command(command, repeats)
