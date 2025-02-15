"""YoLink Dimmer."""

from __future__ import annotations

from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_DIMMER

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YoLink Dimmer from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    entities = [
        YoLinkDimmerEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type == ATTR_DEVICE_DIMMER
    ]
    async_add_entities(entities)


class YoLinkDimmerEntity(YoLinkEntity, LightEntity):
    """YoLink Dimmer Entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = None
    _attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Dimmer entity."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}"

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        if (dimmer_state := state.get("state")) is not None:
            # update _attr_is_on when device report it's state
            self._attr_is_on = dimmer_state == "open"
        if (brightness := state.get("brightness")) is not None:
            self._attr_brightness = round(255 * brightness / 100)
        self.async_write_ha_state()

    async def toggle_light_state(self, state: str, brightness: int | None) -> None:
        """Toggle light state."""
        params: dict[str, Any] = {"state": state}
        if brightness is not None:
            self._attr_brightness = brightness
            params["brightness"] = round(brightness / 255, 2) * 100
        await self.call_device(ClientRequest("setState", params))
        self._attr_is_on = state == "open"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        await self.toggle_light_state("open", brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        await self.toggle_light_state("close", None)
