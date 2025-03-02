"""Support for Elgato lights."""

from __future__ import annotations

from typing import Any

from elgato import ElgatoError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.util import color as color_util

from .const import SERVICE_IDENTIFY
from .coordinator import ElgatoConfigEntry, ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elgato Light based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([ElgatoLight(coordinator)])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_IDENTIFY,
        None,
        ElgatoLight.async_identify.__name__,
    )


class ElgatoLight(ElgatoEntity, LightEntity):
    """Defines an Elgato Light."""

    _attr_name = None
    _attr_min_color_temp_kelvin = 2900  # 344 Mireds
    _attr_max_color_temp_kelvin = 7000  # 143 Mireds

    def __init__(self, coordinator: ElgatoDataUpdateCoordinator) -> None:
        """Initialize Elgato Light."""
        super().__init__(coordinator)
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_unique_id = coordinator.data.info.serial_number

        # Elgato Light supporting color, have a different temperature range
        if (
            self.coordinator.data.info.product_name
            in (
                "Elgato Light Strip",
                "Elgato Light Strip Pro",
            )
            or self.coordinator.data.settings.power_on_hue
            or self.coordinator.data.state.hue is not None
        ):
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
            self._attr_min_color_temp_kelvin = 3500  # 285 Mireds
            self._attr_max_color_temp_kelvin = 6500  # 153 Mireds

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return round((self.coordinator.data.state.brightness * 255) / 100)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if (mired_temperature := self.coordinator.data.state.temperature) is None:
            return None
        return color_util.color_temperature_mired_to_kelvin(mired_temperature)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self.coordinator.data.state.hue is not None:
            return ColorMode.HS

        return ColorMode.COLOR_TEMP

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return (
            self.coordinator.data.state.hue or 0,
            self.coordinator.data.state.saturation or 0,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return self.coordinator.data.state.on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        try:
            await self.coordinator.client.light(on=False)
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while updating the Elgato Light"
            ) from error
        finally:
            await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        temperature_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

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
            and ATTR_COLOR_TEMP_KELVIN not in kwargs
            and self.supported_color_modes
            and ColorMode.HS in self.supported_color_modes
            and self.color_mode == ColorMode.COLOR_TEMP
        ):
            temperature_kelvin = self.color_temp_kelvin

        temperature = (
            None
            if temperature_kelvin is None
            else color_util.color_temperature_kelvin_to_mired(temperature_kelvin)
        )

        try:
            await self.coordinator.client.light(
                on=True,
                brightness=brightness,
                hue=hue,
                saturation=saturation,
                temperature=temperature,
            )
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while updating the Elgato Light"
            ) from error
        finally:
            await self.coordinator.async_refresh()

    async def async_identify(self) -> None:
        """Identify the light, will make it blink."""
        try:
            await self.coordinator.client.identify()
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while identifying the Elgato Light"
            ) from error
