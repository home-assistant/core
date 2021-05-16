"""Support for Elgato lights."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from elgato import Elgato, ElgatoError, Info, Settings, State

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .const import DATA_ELGATO_CLIENT, DOMAIN, SERVICE_IDENTIFY

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elgato Light based on a config entry."""
    elgato: Elgato = hass.data[DOMAIN][entry.entry_id][DATA_ELGATO_CLIENT]
    info = await elgato.info()
    settings = await elgato.settings()
    async_add_entities([ElgatoLight(elgato, info, settings)], True)

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_IDENTIFY,
        {},
        ElgatoLight.async_identify.__name__,
    )


class ElgatoLight(LightEntity):
    """Defines an Elgato Light."""

    def __init__(self, elgato: Elgato, info: Info, settings: Settings) -> None:
        """Initialize Elgato Light."""
        self._info = info
        self._settings = settings
        self._state: State | None = None
        self.elgato = elgato

        self._min_mired = 143
        self._max_mired = 344
        self._supported_color_modes = {COLOR_MODE_COLOR_TEMP}

        # Elgato Light supporting color, have a different temperature range
        if settings.power_on_hue is not None:
            self._supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}
            self._min_mired = 153
            self._max_mired = 285

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        # Return the product name, if display name is not set
        return self._info.display_name or self._info.product_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._info.serial_number

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        assert self._state is not None
        return round((self._state.brightness * 255) / 100)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        assert self._state is not None
        return self._state.temperature

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._min_mired

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        # Elgato lights with color capabilities have a different highest value
        return self._max_mired

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._state and self._state.hue is not None:
            return COLOR_MODE_HS

        return COLOR_MODE_COLOR_TEMP

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if (
            self._state is None
            or self._state.hue is None
            or self._state.saturation is None
        ):
            return None

        return (self._state.hue, self._state.saturation)

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        assert self._state is not None
        return self._state.on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        try:
            await self.elgato.light(on=False)
        except ElgatoError:
            _LOGGER.error("An error occurred while updating the Elgato Light")
            self._state = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        temperature = kwargs.get(ATTR_COLOR_TEMP)

        hue = None
        saturation = None
        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]

        brightness = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = round((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        # For Elgato lights supporting color mode, but in temperature mode;
        # adjusting only brightness make them jump back to color mode.
        # Resending temperature prevents that.
        if (
            brightness
            and ATTR_HS_COLOR not in kwargs
            and ATTR_COLOR_TEMP not in kwargs
            and COLOR_MODE_HS in self.supported_color_modes
            and self.color_mode == COLOR_MODE_COLOR_TEMP
        ):
            temperature = self.color_temp

        try:
            await self.elgato.light(
                on=True,
                brightness=brightness,
                hue=hue,
                saturation=saturation,
                temperature=temperature,
            )
        except ElgatoError:
            _LOGGER.error("An error occurred while updating the Elgato Light")
            self._state = None

    async def async_update(self) -> None:
        """Update Elgato entity."""
        restoring = self._state is None
        try:
            self._state = await self.elgato.state()
            if restoring:
                _LOGGER.info("Connection restored")
        except ElgatoError as err:
            meth = _LOGGER.error if self._state else _LOGGER.debug
            meth("An error occurred while updating the Elgato Light: %s", err)
            self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Elgato Light."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._info.serial_number)},
            ATTR_NAME: self._info.product_name,
            ATTR_MANUFACTURER: "Elgato",
            ATTR_MODEL: self._info.product_name,
            ATTR_SW_VERSION: f"{self._info.firmware_version} ({self._info.firmware_build_number})",
        }

    async def async_identify(self) -> None:
        """Identify the light, will make it blink."""
        try:
            await self.elgato.identify()
        except ElgatoError:
            _LOGGER.exception("An error occurred while identifying the Elgato Light")
            self._state = None
