"""Support for dobiss lights."""

import logging
from typing import Any

from dobissapi import DobissAnalogOutput, DobissLight, DobissOutput

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dobiss lights."""
    _LOGGER.debug("Setting up light component of %s", DOMAIN)

    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    light_entities = dobiss.get_devices_by_type(DobissLight)
    entities = []
    for device in light_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (device.address in (210, 211))
        ):
            continue
        entities.append(HADobissLight(device))

    # wrap analog output in lights for now...
    analog_entities = dobiss.get_devices_by_type(DobissAnalogOutput)
    entities.extend(HADobissLight(device) for device in analog_entities)

    if entities:
        async_add_entities(entities)


class HADobissLight(LightEntity):
    """Dobiss light device."""

    should_poll = False

    def __init__(self, dobisslight: DobissOutput) -> None:
        """Init dobiss light device."""
        super().__init__()
        self._dobisslight = dobisslight
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ONOFF}
        if self._dobisslight.dimmable:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._dobisslight.object_id)},
            name=self.name,
            manufacturer="dobiss",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return supported attributes."""
        return self._dobisslight.attributes

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._dobisslight.register_callback(self.async_write_ha_state)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.signal_handler)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._dobisslight.remove_callback(self.async_write_ha_state)

    async def signal_handler(self, data: dict[str, Any]) -> None:
        """Handle domain-specific signal by calling appropriate method."""
        entity_ids = data[ATTR_ENTITY_ID]

        if entity_ids == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            await getattr(self, data["method"])(**params)

    async def turn_on_service(
        self,
        brightness: int | None = None,
        delayon: int | None = None,
        delayoff: int | None = None,
        from_pir: bool = False,
    ) -> None:
        """Turn on the light with optional parameters."""
        await self._dobisslight.turn_on(
            brightness=brightness, delayon=delayon, delayoff=delayoff, from_pir=from_pir
        )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self._dobisslight.dimmable:
            return None
        # dobiss works from 0-100, ha from 0-255
        return int((self._dobisslight.value / 100) * 255)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._dobisslight.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        # dobiss works from 0-100, ha from 0-255
        raw_brightness = kwargs.get(ATTR_BRIGHTNESS)
        if raw_brightness is not None:
            brightness = int((raw_brightness / 255) * 100)
        else:
            brightness = 100
        await self._dobisslight.turn_on(brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._dobisslight.turn_off()

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if isinstance(self._dobisslight, DobissAnalogOutput):
            return "mdi:hvac"
        return super().icon or "mdi:lightbulb"

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._dobisslight.dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return self._attr_supported_color_modes

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._dobisslight.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._dobisslight.object_id
