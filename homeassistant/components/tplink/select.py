"""Demo platform that offers a fake select entity."""

from __future__ import annotations

from kasa import Feature, SmartDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
    _entities_for_device_and_its_children,
    async_refresh_after,
)
from .models import TPLinkData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Choice,
        entity_class=Select,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class Select(CoordinatedTPLinkEntity, SelectEntity):
    """Representation of a tplink select entity."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        # TODO: generalize creation of entitydescription into CoordinatedTPLinkEntity?
        self.entity_description = SelectEntityDescription(
            key=feature.id,
            translation_key=feature.id,
            name=feature.name,
            icon=feature.icon,
            options=feature.choices,
            **feature.hass_compat.dict(),
        )

        self._async_update_attrs()

    @async_refresh_after
    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        await self._feature.set_value(option)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_current_option = self._feature.value
