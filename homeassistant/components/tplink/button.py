"""Demo platform that offers a fake button entity."""

from __future__ import annotations

from kasa import Feature, SmartDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, _entities_for_device_and_its_children
from .models import TPLinkData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Action,
        entity_class=Button,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class Button(CoordinatedTPLinkEntity, ButtonEntity):
    """Representation of a TPLink button entity."""

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
        self.entity_description = ButtonEntityDescription(
            key=feature.id,
            translation_key=feature.id,
            name=feature.name,
            icon=feature.icon,
            **feature.hass_compat.dict(),
        )

    async def async_press(self) -> None:
        """Execute action."""
        await self._feature.set_value(True)

    def _async_update_attrs(self):
        """No need to update anything."""
