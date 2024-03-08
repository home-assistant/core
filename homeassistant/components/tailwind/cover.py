"""Cover entity platform for Tailwind."""
from __future__ import annotations

from typing import Any

from gotailwind import (
    TailwindDoorDisabledError,
    TailwindDoorLockedOutError,
    TailwindDoorOperationCommand,
    TailwindDoorState,
    TailwindError,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TailwindDataUpdateCoordinator
from .entity import TailwindDoorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tailwind cover based on a config entry."""
    coordinator: TailwindDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TailwindDoorCoverEntity(coordinator, door_id)
        for door_id in coordinator.data.doors
    )


class TailwindDoorCoverEntity(TailwindDoorEntity, CoverEntity):
    """Representation of a Tailwind door binary sensor entity."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_is_closing = False
    _attr_is_opening = False
    _attr_name = None
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return (
            self.coordinator.data.doors[self.door_id].state == TailwindDoorState.CLOSED
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door.

        The Tailwind operating command will await the confirmation of the
        door being opened before returning.
        """
        self._attr_is_opening = True
        self.async_write_ha_state()
        try:
            await self.coordinator.tailwind.operate(
                door=self.coordinator.data.doors[self.door_id],
                operation=TailwindDoorOperationCommand.OPEN,
            )
        except TailwindDoorDisabledError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="door_disabled",
            ) from exc
        except TailwindDoorLockedOutError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="door_locked_out",
            ) from exc
        except TailwindError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from exc
        finally:
            self._attr_is_opening = False
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door.

        The Tailwind operating command will await the confirmation of the
        door being closed before returning.
        """
        self._attr_is_closing = True
        self.async_write_ha_state()
        try:
            await self.coordinator.tailwind.operate(
                door=self.coordinator.data.doors[self.door_id],
                operation=TailwindDoorOperationCommand.CLOSE,
            )
        except TailwindDoorDisabledError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="door_disabled",
            ) from exc
        except TailwindDoorLockedOutError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="door_locked_out",
            ) from exc
        except TailwindError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from exc
        finally:
            self._attr_is_closing = False
        await self.coordinator.async_request_refresh()
