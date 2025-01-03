"""Platform for light integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COLOR,
    ATTR_ON,
    ATTR_SECTION_ID,
    CONF_SECTIONS,
    DOMAIN as DEVICE_DOMAIN,
)
from .coordinator import ScpRpiDataUpdateCoordinator

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="admin"): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add all entities representing strip sections."""
    coordinator = entry.runtime_data
    sections = entry.data[CONF_SECTIONS]
    device_name = entry.data[CONF_NAME]
    async_add_entities(
        [
            Section(coordinator, entry.entry_id, device_name, index)
            for index, _ in enumerate(sections)
        ]
    )


# TOD: find a way to disable setting bright percentage just turning on/off (maybe set fixed bright at 100%)


class Section(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(
        self,
        coordinator: ScpRpiDataUpdateCoordinator,
        entry_id: str,
        device_name: str,
        section: int,
    ) -> None:
        """Initialize the section.

        entity_id will be automatically set lower-snake-casing the name of the device
        """
        # TOD set required section attributes in order to communicate with device to execute operations
        self.coordinator = coordinator
        self._light = None  # light
        self._name = f"{device_name} section {section}"
        # TOD set correct entity id for example generating an unique or getting from external service (sc-rpi)
        # TOD investigate for what its needed this attribute
        self._attr_unique_id = f"{entry_id}-strip-section-{section}"
        # TOD define the correct type for _state
        self._state: dict = {}
        self._section = section
        self._brightness = 4
        # associate entity to device
        self._attr_device_info = DeviceInfo(identifiers={(DEVICE_DOMAIN, entry_id)})
        self._attr_color_mode = ColorMode.RGB
        self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.BRIGHTNESS}

    @property
    def device_info(self):
        """Return device information about this entity."""
        return self._attr_device_info

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state is not None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return (0, 255, 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: dict[str, Any] = {
            ATTR_ON: True,
            ATTR_SECTION_ID: self._section,
            ATTR_COLOR: kwargs[ATTR_RGB_COLOR],
        }

        # if ATTR_RGB_COLOR in kwargs:
        #    data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGB_COLOR]

        # if ATTR_RGBW_COLOR in kwargs:
        #    data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGBW_COLOR]

        # if ATTR_BRIGHTNESS in kwargs:
        #    data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        await self.coordinator.scrpi.section(**data)

    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        # self._light.update()
        # self._state = self._light.is_on()
        # self._brightness = self._light.brightness
