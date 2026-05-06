"""Cover platform for Fluss+ devices with a position sensor."""

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FlussApiClientError, FlussConfigEntry
from .entity import FlussEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss covers for devices that report a position sensor."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)
    known: set[str] = set()

    @callback
    def _add_covers() -> None:
        new_entities: list[FlussCover] = []
        for device_id, device in coordinator.data.items():
            if device_id in known or not device.has_position_sensor:
                continue
            # Once a device gains the position sensor it must surface as a
            # cover, never a button. Remove any prior button registry entry
            # left over from an earlier install or from a refresh that
            # registered the device before its capability was known.
            button_entity_id = entity_registry.async_get_entity_id(
                "button", DOMAIN, device_id
            )
            if button_entity_id is not None:
                entity_registry.async_remove(button_entity_id)
            known.add(device_id)
            new_entities.append(FlussCover(coordinator, device))
        if new_entities:
            async_add_entities(new_entities)

    _add_covers()
    entry.async_on_unload(coordinator.async_add_listener(_add_covers))


class FlussCover(FlussEntity, CoverEntity):
    """Representation of a Fluss+ cover (garage door / gate)."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_name = None
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is closed."""
        return self.device.is_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self.coordinator.api.async_open_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.coordinator.async_schedule_device_refresh(self.device_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self.coordinator.api.async_close_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.coordinator.async_schedule_device_refresh(self.device_id)
