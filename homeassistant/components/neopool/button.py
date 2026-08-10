"""Button platform for the NeoPool integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, override

from neopool_modbus.capabilities import is_hydrolysis_present
from neopool_modbus.exceptions import NeoPoolError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity
from .helpers import prepare_device_time

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NeoPoolButtonEntityDescription(ButtonEntityDescription):
    """Describes a NeoPool button entity."""

    supported_fn: Callable[[dict[str, Any]], bool] | None = None
    press_fn: Callable[[NeoPoolButton], Awaitable[None]]


async def _press_sync_time(entity: NeoPoolButton) -> None:
    """Push the current HA wall-clock to the device."""
    _LOGGER.debug("Syncing time with device")
    await entity.coordinator.client.async_sync_device_time(
        prepare_device_time(entity.hass)
    )


async def _press_clear_errors(entity: NeoPoolButton) -> None:
    """Clear all possible device errors."""
    _LOGGER.debug("Clearing all possible errors")
    await entity.coordinator.client.async_clear_errors()


async def _press_reset_cell_partial(entity: NeoPoolButton) -> None:
    """Reset the partial cell-runtime counter on the device."""
    _LOGGER.info(
        "Resetting partial cell runtime counter on device '%s'",
        entity.coordinator.config_entry.title,
    )
    await entity.coordinator.client.async_reset_user_counters()


BUTTON_DESCRIPTIONS: dict[str, NeoPoolButtonEntityDescription] = {
    "SYNC_TIME": NeoPoolButtonEntityDescription(
        key="SYNC_TIME",
        translation_key="sync_time",
        entity_category=EntityCategory.CONFIG,
        press_fn=_press_sync_time,
    ),
    "MBF_ESCAPE": NeoPoolButtonEntityDescription(
        key="MBF_ESCAPE",
        translation_key="escape",
        entity_category=EntityCategory.CONFIG,
        press_fn=_press_clear_errors,
    ),
    "RESET_CELL_PARTIAL": NeoPoolButtonEntityDescription(
        key="RESET_CELL_PARTIAL",
        translation_key="reset_cell_partial",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
        press_fn=_press_reset_cell_partial,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool button entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NeoPoolButton(coordinator, key, desc)
        for key, desc in BUTTON_DESCRIPTIONS.items()
        if desc.supported_fn is None or desc.supported_fn(coordinator.data)
    )


class NeoPoolButton(NeoPoolEntity, ButtonEntity):
    """Representation of a NeoPool button entity."""

    entity_description: NeoPoolButtonEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolButtonEntityDescription,
    ) -> None:
        """Initialize the NeoPool button entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    @override
    async def async_press(self) -> None:
        """Dispatch to the description's press handler."""
        try:
            await self.entity_description.press_fn(self)
        except (NeoPoolError, OSError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="modbus_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
