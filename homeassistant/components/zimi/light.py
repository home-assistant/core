"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support.
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Light platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    # host = config_entry.data[CONF_HOST]
    # port = config_entry.data[CONF_PORT]

    debug = config_entry.data.get("debug", False)

    controller: ZimiController = hass.data[CONTROLLER]

    entities = []

    # for key, device in controller.api.devices.items().:
    for device in controller.controller.lights:
        entities.append(ZimiLight(device, debug=debug))  # noqa: PERF401

    async_add_entities(entities)


class ZimiLight(LightEntity):
    """Representation of a Zimi Light."""

    def __init__(self, light, debug=False) -> None:
        """Initialize an ZimiLight."""

        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        self._attr_unique_id = light.identifier
        self._attr_should_poll = False
        self._light = light
        self._light.subscribe(self)
        self._state = False
        self._brightness = None
        if self._light.type == "dimmer":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.identifier)},
            name=self._light.name,
            suggested_area=self._light.room,
        )
        self.update()
        self.logger.debug("__init__(%s) in %s", self.name, self._light.room)

    def __del__(self):
        """Cleanup ZimiLight with removal of notification."""
        self._light.unsubscribe(self)

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name.strip()

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._light.is_connected

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """

        self.logger.debug(
            "turn_on(brightness=%d) for %s",
            kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255,
            self.name,
        )

        if self._light.type == "dimmer":
            await self._light.set_brightness(
                kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255
            )
        else:
            await self._light.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        self.logger.debug("turn_off() for %s", self.name)

        await self._light.turn_off()

    def notify(self, _observable):
        """Receive notification from light device that state has changed."""

        self.logger.debug("notification() for %s received", self.name)
        self.schedule_update_ha_state(force_refresh=True)

    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """

        self._name = self._light.name
        self._state = self._light.is_on
        if self._light.type == "dimmer":
            if self._light.brightness:
                self._brightness = self._light.brightness * 255 / 100
