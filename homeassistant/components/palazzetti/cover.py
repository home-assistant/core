"""Support for Palazzetti cover (motorized door)."""

from typing import Any, override

from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PalazzettiConfigEntry, PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PalazzettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Palazzetti cover platform."""

    coordinator = config_entry.runtime_data
    if coordinator.client.has_door_control:
        async_add_entities([PalazzettiCoverEntity(coordinator)])


class PalazzettiCoverEntity(PalazzettiEntity, CoverEntity):
    """Representation of a Palazzetti motorized door cover entity."""

    _attr_translation_key = "door"
    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
    ) -> None:
        """Initialize a Palazzetti cover."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.unique_id

    @property
    @override
    def is_closed(self) -> bool:
        """Return true if the door is closed."""
        return not self.coordinator.client.is_door_open

    async def _async_set_door(self, open_door: bool) -> None:
        """Set the door state."""
        try:
            if not await self.coordinator.client.set_door(open_door):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )
        except (CommunicationError, ValidationError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door."""
        await self._async_set_door(True)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door."""
        await self._async_set_door(False)
