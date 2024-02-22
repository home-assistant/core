"""Support for TPLink switch entities."""

from __future__ import annotations

import logging
from typing import Any, cast

from kasa import Feature, FeatureType, SmartDevice, SmartPlug

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after
from .models import TPLinkData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = cast(SmartPlug, parent_coordinator.device)
    entities: list = []

    def _switches_for_device(dev, parent: SmartDevice = None) -> list[Switch]:
        switches = [
            Switch(dev, data.parent_coordinator, id_, feat, parent=parent)
            for id_, feat in dev.features.items()
            if feat.type == FeatureType.Switch
        ]
        # TODO: a way to filter state switch for platforms with their own main controls:
        #  lights and fans?
        return switches

    if device.children:
        _LOGGER.debug("Initializing device with %s children", len(device.children))
        for child in device.children:
            entities.extend(_switches_for_device(child, parent=device))

    entities.extend(_switches_for_device(device))

    async_add_entities(entities)


class Switch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        id_: str,
        feature: Feature,
        parent: SmartDevice = None,
    ):
        """Initialize the switch."""
        super().__init__(device, coordinator, parent=parent)
        self._device = device
        self._feature = feature
        self._attr_unique_id = f"{legacy_device_id(device)}_new_{id_}"
        self._attr_entity_category = (
            EntityCategory.CONFIG
        )  # TODO: read from the feature
        if feature.name == "State":  # Main switch of the device has no category.
            self._attr_entity_category = None

        self.entity_description = SwitchEntityDescription(
            key=id_, name=feature.name, icon=feature.icon
        )
        self._async_update_attrs()

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED switch on."""
        await self._feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED switch off."""
        await self._feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        is_on = self._feature.value

        icon = self._feature.icon
        # TODO: hacky way to support on/off icons. maybe this should be removed?
        if icon and "{state}" in icon:
            icon = icon.replace("{state}", "on" if is_on else "off")
        self._attr_icon = icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()
