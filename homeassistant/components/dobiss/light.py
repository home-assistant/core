"""Support for dobiss lights."""

import logging
from typing import Any

from dobissapi import DobissAnalogOutput, DobissLight, DobissOutput

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dobiss lights."""
    _LOGGER.debug("Setting up light component of %s", DOMAIN)

    client = config_entry.runtime_data
    dobiss = client.api

    light_entities = dobiss.get_devices_by_type(DobissLight)
    entities = [DobissLightEntity(device) for device in light_entities]

    # wrap analog output in lights for now...
    analog_entities = dobiss.get_devices_by_type(DobissAnalogOutput)
    entities.extend(DobissLightEntity(device) for device in analog_entities)

    if entities:
        async_add_entities(entities)


class DobissLightEntity(LightEntity):
    """Representation of a Dobiss light or analog output."""

    _attr_should_poll = False

    def __init__(self, device: DobissOutput) -> None:
        """Initialize the Dobiss light."""
        self._device = device

        self._attr_unique_id = device.object_id
        self._attr_name = None
        self._attr_has_entity_name = True

        self._attr_supported_color_modes = (
            {ColorMode.BRIGHTNESS} if device.dimmable else {ColorMode.ONOFF}
        )
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if device.dimmable else ColorMode.ONOFF
        )

        self._attr_icon = (
            "mdi:hvac" if isinstance(device, DobissAnalogOutput) else "mdi:lightbulb"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.object_id)},
            name=device.name,
            manufacturer="dobiss",
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        self._device.register_callback(self.async_write_ha_state)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self._signal_handler)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        self._device.remove_callback(self.async_write_ha_state)

    async def _signal_handler(self, data: dict[str, Any]) -> None:
        """Handle dispatcher signal."""
        entity_ids = data.get("entity_id")
        if entity_ids not in (ENTITY_MATCH_ALL, self.entity_id):
            return

        method = data.get("method")
        if method:
            params = {
                key: value
                for key, value in data.items()
                if key not in ("entity_id", "method")
            }
            await getattr(self, method)(**params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        value = int((brightness / 255) * 100) if brightness is not None else 100
        await self._device.turn_on(brightness=value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.turn_off()

    @property
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return self._device.is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness level (0..255)."""
        if not self._device.dimmable:
            return None
        return int((self._device.value / 100) * 255)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return self._device.attributes

    async def turn_on_service(
        self,
        brightness: int | None = None,
        delayon: int | None = None,
        delayoff: int | None = None,
        from_pir: bool = False,
    ) -> None:
        """Turn on the light with optional parameters (called via dispatcher)."""
        await self._device.turn_on(
            brightness=brightness,
            delayon=delayon,
            delayoff=delayoff,
            from_pir=from_pir,
        )
