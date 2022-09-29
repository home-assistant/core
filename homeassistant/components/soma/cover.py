"""Support for Soma Covers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import API, DEVICES, DOMAIN, SomaEntity
from .utils import is_api_response_success


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Soma cover platform."""

    api = hass.data[DOMAIN][API]
    devices = hass.data[DOMAIN][DEVICES]
    entities: list[SomaTilt | SomaShade] = []

    for device in devices:
        # Assume a shade device if the type is not present in the api response (Connect <2.2.6)
        if "type" in device and device["type"].lower() == "tilt":
            entities.append(SomaTilt(device, api))
        else:
            entities.append(SomaShade(device, api))

    async_add_entities(entities, True)


class SomaTilt(SomaEntity, CoverEntity):
    """Representation of a Soma Tilt device."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    @property
    def current_cover_tilt_position(self) -> int:
        """Return the current cover tilt position."""
        return self.current_position

    @property
    def is_closed(self) -> bool:
        """Return if the cover tilt is closed."""
        return self.current_position == 0

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        response = self.api.set_shade_position(self.device["mac"], 100)
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while closing the cover ({self.name}): {response["msg"]}'
            )
        self.set_position(0)

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        response = self.api.set_shade_position(self.device["mac"], -100)
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while opening the cover ({self.name}): {response["msg"]}'
            )
        self.set_position(100)

    def stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        response = self.api.stop_shade(self.device["mac"])
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while stopping the cover ({self.name}): {response["msg"]}'
            )
        # Set cover position to some value where up/down are both enabled
        self.set_position(50)

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        # 0 -> Closed down (api: 100)
        # 50 -> Fully open (api: 0)
        # 100 -> Closed up (api: -100)
        target_api_position = 100 - ((kwargs[ATTR_TILT_POSITION] / 50) * 100)
        response = self.api.set_shade_position(self.device["mac"], target_api_position)
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while setting the cover position ({self.name}): {response["msg"]}'
            )
        self.set_position(kwargs[ATTR_TILT_POSITION])

    async def async_update(self) -> None:
        """Update the entity with the latest data."""
        response = await self.get_shade_state_from_api()

        api_position = int(response["position"])

        if "closed_upwards" in response.keys():
            self.current_position = 50 + ((api_position * 50) / 100)
        else:
            self.current_position = 50 - ((api_position * 50) / 100)


class SomaShade(SomaEntity, CoverEntity):
    """Representation of a Soma Shade device."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        return self.current_position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.current_position == 0

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        response = self.api.set_shade_position(self.device["mac"], 100)
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while closing the cover ({self.name}): {response["msg"]}'
            )

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        response = self.api.set_shade_position(self.device["mac"], 0)
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while opening the cover ({self.name}): {response["msg"]}'
            )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        response = self.api.stop_shade(self.device["mac"])
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while stopping the cover ({self.name}): {response["msg"]}'
            )
        # Set cover position to some value where up/down are both enabled
        self.set_position(50)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover shutter to a specific position."""
        self.current_position = kwargs[ATTR_POSITION]
        response = self.api.set_shade_position(
            self.device["mac"], 100 - kwargs[ATTR_POSITION]
        )
        if not is_api_response_success(response):
            raise HomeAssistantError(
                f'Error while setting the cover position ({self.name}): {response["msg"]}'
            )

    async def async_update(self) -> None:
        """Update the cover with the latest data."""
        response = await self.get_shade_state_from_api()

        self.current_position = 100 - int(response["position"])
