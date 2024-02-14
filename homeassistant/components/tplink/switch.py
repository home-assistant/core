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
    if device.is_strip:
        # Historically we only add the children if the device is a strip
        _LOGGER.debug("Initializing strip with %s sockets", len(device.children))
        entities.extend(
            SmartPlugSwitchChild(device, parent_coordinator, child)
            for child in device.children
        )
    elif device.is_plug:
        entities.append(SmartPlugSwitch(device, parent_coordinator))

    new_switches = [
        Switch(device, data.parent_coordinator, id_, feat)
        for id_, feat in device.features.items()
        if feat.type == FeatureType.Switch
    ]

    async_add_entities(entities + new_switches)


class Switch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        id_: str,
        feature: Feature,
    ):
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self._device = device
        self._feature = feature
        self._attr_unique_id = f"{legacy_device_id(device)}_new_{id_}"
        self._attr_entity_category = EntityCategory.CONFIG
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
        # TODO: hacky way to support on/off icons..
        if "{state}" in icon:
            icon = icon.replace("{state}", "on" if is_on else "off")
        self._attr_icon = icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


class SmartPlugSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    _attr_name: str | None = None

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        # For backwards compat with pyHS100
        self._attr_unique_id = legacy_device_id(device)
        self._async_update_attrs()

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.device.turn_on()

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.device.turn_off()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self.device.is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


class SmartPlugSwitchChild(SmartPlugSwitch):
    """Representation of an individual plug of a TPLink Smart Plug strip."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        plug: SmartDevice,
    ) -> None:
        """Initialize the child switch."""
        self._plug = plug
        super().__init__(device, coordinator)
        self._attr_unique_id = legacy_device_id(plug)
        self._attr_name = plug.alias

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the child switch on."""
        await self._plug.turn_on()

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the child switch off."""
        await self._plug.turn_off()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._plug.is_on
