"""The Twinkly light component."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError
from ttls.client import Twinkly

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_CLIENT,
    DATA_DEVICE_INFO,
    DEV_LED_PROFILE,
    DEV_MODEL,
    DEV_NAME,
    DEV_PROFILE_RGB,
    DEV_PROFILE_RGBW,
    DOMAIN,
    ENTRY_DATA_HOST,
    ENTRY_DATA_ID,
    ENTRY_DATA_MODEL,
    ENTRY_DATA_NAME,
    HIDDEN_DEV_VALUES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setups an entity from a config entry (UI config flow)."""

    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    device_info = hass.data[DOMAIN][config_entry.entry_id][DATA_DEVICE_INFO]

    entity = TwinklyLight(config_entry, client, device_info)

    async_add_entities([entity], update_before_add=True)


class TwinklyLight(LightEntity):
    """Implementation of the light for the Twinkly service."""

    def __init__(
        self,
        conf: ConfigEntry,
        client: Twinkly,
        device_info,
    ) -> None:
        """Initialize a TwinklyLight entity."""
        self._id = conf.data[ENTRY_DATA_ID]
        self._conf = conf

        if device_info.get(DEV_LED_PROFILE) == DEV_PROFILE_RGBW:
            self._attr_supported_color_modes = {COLOR_MODE_RGBW}
            self._attr_color_mode = COLOR_MODE_RGBW
            self._attr_rgbw_color = (255, 255, 255, 0)
        elif device_info.get(DEV_LED_PROFILE) == DEV_PROFILE_RGB:
            self._attr_supported_color_modes = {COLOR_MODE_RGB}
            self._attr_color_mode = COLOR_MODE_RGB
            self._attr_rgb_color = (255, 255, 255)
        else:
            self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS

        # Those are saved in the config entry in order to have meaningful values even
        # if the device is currently offline.
        # They are expected to be updated using the device_info.
        self._name = conf.data[ENTRY_DATA_NAME]
        self._model = conf.data[ENTRY_DATA_MODEL]

        self._client = client

        # Set default state before any update
        self._is_on = False
        self._is_available = False
        self._attributes: dict[Any, Any] = {}

    @property
    def available(self) -> bool:
        """Get a boolean which indicates if this entity is currently available."""
        return self._is_available

    @property
    def unique_id(self) -> str | None:
        """Id of the device."""
        return self._id

    @property
    def name(self) -> str:
        """Name of the device."""
        return self._name if self._name else "Twinkly light"

    @property
    def model(self) -> str:
        """Name of the device."""
        return self._model

    @property
    def icon(self) -> str:
        """Icon of the device."""
        return "mdi:string-lights"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            manufacturer="LEDWORKS",
            model=self.model,
            name=self.name,
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict:
        """Return device specific state attributes."""

        attributes = self._attributes

        return attributes

    async def async_turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(int(kwargs[ATTR_BRIGHTNESS]) / 2.55)

            # If brightness is 0, the twinkly will only "disable" the brightness,
            # which means that it will be 100%.
            if brightness == 0:
                await self._client.turn_off()
                return

            await self._client.set_brightness(brightness)

        if ATTR_RGBW_COLOR in kwargs:
            if kwargs[ATTR_RGBW_COLOR] != self._attr_rgbw_color:
                self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]

                if isinstance(self._attr_rgbw_color, tuple):

                    await self._client.interview()
                    # Reagarrange from rgbw to wrgb
                    await self._client.set_static_colour(
                        (
                            self._attr_rgbw_color[3],
                            self._attr_rgbw_color[0],
                            self._attr_rgbw_color[1],
                            self._attr_rgbw_color[2],
                        )
                    )

        if ATTR_RGB_COLOR in kwargs:
            if kwargs[ATTR_RGB_COLOR] != self._attr_rgb_color:
                self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]

                if isinstance(self._attr_rgb_color, tuple):

                    await self._client.interview()
                    # Reagarrange from rgbw to wrgb
                    await self._client.set_static_colour(self._attr_rgb_color)

        if not self._is_on:
            await self._client.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn device off."""
        await self._client.turn_off()

    async def async_update(self) -> None:
        """Asynchronously updates the device properties."""
        _LOGGER.debug("Updating '%s'", self._client.host)

        try:
            self._is_on = await self._client.is_on()

            brightness = await self._client.get_brightness()
            brightness_value = (
                int(brightness["value"]) if brightness["mode"] == "enabled" else 100
            )

            self._attr_brightness = (
                int(round(brightness_value * 2.55)) if self._is_on else 0
            )

            device_info = await self._client.get_details()

            if (
                DEV_NAME in device_info
                and DEV_MODEL in device_info
                and (
                    device_info[DEV_NAME] != self._name
                    or device_info[DEV_MODEL] != self._model
                )
            ):
                self._name = device_info[DEV_NAME]
                self._model = device_info[DEV_MODEL]

                # If the name has changed, persist it in conf entry,
                # so we will be able to restore this new name if hass is started while the LED string is offline.
                self.hass.config_entries.async_update_entry(
                    self._conf,
                    data={
                        ENTRY_DATA_HOST: self._client.host,  # this cannot change
                        ENTRY_DATA_ID: self._id,  # this cannot change
                        ENTRY_DATA_NAME: self._name,
                        ENTRY_DATA_MODEL: self._model,
                    },
                )

            for key, value in device_info.items():
                if key not in HIDDEN_DEV_VALUES:
                    self._attributes[key] = value

            if not self._is_available:
                _LOGGER.info("Twinkly '%s' is now available", self._client.host)

            # We don't use the echo API to track the availability since we already have to pull
            # the device to get its state.
            self._is_available = True
        except (asyncio.TimeoutError, ClientError):
            # We log this as "info" as it's pretty common that the christmas light are not reachable in july
            if self._is_available:
                _LOGGER.info(
                    "Twinkly '%s' is not reachable (client error)", self._client.host
                )
            self._is_available = False
