"""Support for LED lights."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable, Dict, List

from elgato import Elgato, ElgatoError, Info, State

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_ON,
    ATTR_SOFTWARE_VERSION,
    ATTR_TEMPERATURE,
    DATA_ELGATO_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Elgato Key Light based on a config entry."""
    elgato: Elgato = hass.data[DOMAIN][entry.entry_id][DATA_ELGATO_CLIENT]
    info = await elgato.info()
    async_add_entities([ElgatoLight(elgato, info)], True)


class ElgatoLight(LightEntity):
    """Defines a Elgato Key Light."""

    def __init__(
        self,
        elgato: Elgato,
        info: Info,
    ):
        """Initialize Elgato Key Light."""
        self._brightness: int | None = None
        self._info: Info = info
        self._state: bool | None = None
        self._temperature: int | None = None
        self._available = True
        self.elgato = elgato

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        # Return the product name, if display name is not set
        if not self._info.display_name:
            return self._info.product_name
        return self._info.display_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._info.serial_number

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return self._brightness

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        return self._temperature

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return 143

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return 344

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self._state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.async_turn_on(on=False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: Dict[str, bool | int] = {ATTR_ON: True}

        if ATTR_ON in kwargs:
            data[ATTR_ON] = kwargs[ATTR_ON]

        if ATTR_COLOR_TEMP in kwargs:
            data[ATTR_TEMPERATURE] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = round((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        try:
            await self.elgato.light(**data)
        except ElgatoError:
            _LOGGER.error("An error occurred while updating the Elgato Key Light")
            self._available = False

    async def async_update(self) -> None:
        """Update Elgato entity."""
        try:
            state: State = await self.elgato.state()
        except ElgatoError:
            if self._available:
                _LOGGER.error("An error occurred while updating the Elgato Key Light")
            self._available = False
            return

        self._available = True
        self._brightness = round((state.brightness * 255) / 100)
        self._state = state.on
        self._temperature = state.temperature

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Elgato Key Light."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._info.serial_number)},
            ATTR_NAME: self._info.product_name,
            ATTR_MANUFACTURER: "Elgato",
            ATTR_MODEL: self._info.product_name,
            ATTR_SOFTWARE_VERSION: f"{self._info.firmware_version} ({self._info.firmware_build_number})",
        }
