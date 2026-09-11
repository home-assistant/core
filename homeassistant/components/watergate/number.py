"""Support for Watergate numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import AutoShutOffState

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WatergateConfigEntry, WatergateDataCoordinator
from .entity import WatergateEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class WatergateNumberEntityDescription(NumberEntityDescription):
    """Description for Watergate number entities."""

    value_fn: Callable[[AutoShutOffState], int]
    set_fn: Callable[[WatergateLocalApiClient, int], Awaitable[bool]]


DESCRIPTIONS: tuple[WatergateNumberEntityDescription, ...] = (
    WatergateNumberEntityDescription(
        key="auto_shut_off_volume_threshold",
        translation_key="auto_shut_off_volume_threshold",
        device_class=NumberDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        native_min_value=1,
        native_max_value=10000,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda auto_shut_off: auto_shut_off.volume_threshold,
        set_fn=lambda client, value: client.async_update_auto_shut_off(volume=value),
    ),
    WatergateNumberEntityDescription(
        key="auto_shut_off_duration_threshold",
        translation_key="auto_shut_off_duration_threshold",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=1440,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda auto_shut_off: auto_shut_off.duration_threshold,
        set_fn=lambda client, value: client.async_update_auto_shut_off(duration=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Watergate number entities."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        SonicAutoShutOffThreshold(coordinator, description)
        for description in DESCRIPTIONS
    )


class SonicAutoShutOffThreshold(WatergateEntity, NumberEntity):
    """Number to configure an auto-shut-off threshold."""

    entity_description: WatergateNumberEntityDescription

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entity_description: WatergateNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    @override
    def native_value(self) -> int:
        """Return the configured threshold."""
        return self.entity_description.value_fn(self.coordinator.data.auto_shut_off)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new threshold."""
        try:
            await self.entity_description.set_fn(self._api_client, round(value))
        except WatergateApiException as exc:
            raise HomeAssistantError("Failed to update auto shut-off") from exc
        await self.coordinator.async_request_refresh()
