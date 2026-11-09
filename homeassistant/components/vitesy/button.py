"""Button platform for the Vitesy integration."""

from dataclasses import dataclass
from typing import override

from aiovitesy.exceptions import VitesyError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VitesyConfigEntry, VitesyDataUpdateCoordinator
from .entity import VitesyEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VitesyButtonEntityDescription(ButtonEntityDescription):
    """Describes a Vitesy maintenance reset button."""

    component: str


BUTTONS: tuple[VitesyButtonEntityDescription, ...] = (
    VitesyButtonEntityDescription(
        key="filter_changed",
        translation_key="filter_changed",
        entity_category=EntityCategory.CONFIG,
        component="filter",
    ),
    VitesyButtonEntityDescription(
        key="fridge_cleaned",
        translation_key="fridge_cleaned",
        entity_category=EntityCategory.CONFIG,
        component="fridge",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitesyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitesy buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitesyButton(coordinator, device_id, description)
        for device_id, device in coordinator.data.items()
        for description in BUTTONS
        if description.component in device.maintenance
    )


class VitesyButton(VitesyEntity, ButtonEntity):
    """Button marking a Vitesy maintenance task as done."""

    entity_description: VitesyButtonEntityDescription

    def __init__(
        self,
        coordinator: VitesyDataUpdateCoordinator,
        device_id: str,
        description: VitesyButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @override
    async def async_press(self) -> None:
        """Start the next maintenance period for this component."""
        try:
            await self.coordinator.api.reset_maintenance(
                self._device_id, self.entity_description.component
            )
        except VitesyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reset_maintenance_failed",
            ) from err
        await self.coordinator.async_request_refresh()
