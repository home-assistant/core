"""Support for Elgato lights."""
from __future__ import annotations

from typing import Any

from elgato import Elgato, ElgatoError, Info, Settings, State

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import HomeAssistantElgatoData
from .const import DOMAIN, SERVICE_IDENTIFY
from .entity import ElgatoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elgato Light based on a config entry."""
    data: HomeAssistantElgatoData = hass.data[DOMAIN][entry.entry_id]
    settings = await data.client.settings()
    async_add_entities(
        [
            ElgatoLight(
                data.coordinator,
                data.client,
                data.info,
                entry.data.get(CONF_MAC),
                settings,
            )
        ],
        True,
    )

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_IDENTIFY,
        {},
        ElgatoLight.async_identify.__name__,
    )


class ElgatoLight(
    ElgatoEntity, CoordinatorEntity[DataUpdateCoordinator[State]], LightEntity
):
    """Defines an Elgato Light."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        client: Elgato,
        info: Info,
        mac: str | None,
        settings: Settings,
    ) -> None:
        """Initialize Elgato Light."""
        super().__init__(client, info, mac)
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_min_mireds = 143
        self._attr_max_mireds = 344
        self._attr_name = info.display_name or info.product_name
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_unique_id = info.serial_number

        # Elgato Light supporting color, have a different temperature range
        if settings.power_on_hue is not None:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
            self._attr_min_mireds = 153
            self._attr_max_mireds = 285

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return round((self.coordinator.data.brightness * 255) / 100)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        return self.coordinator.data.temperature

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self.coordinator.data.hue is not None:
            return ColorMode.HS

        return ColorMode.COLOR_TEMP

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return (self.coordinator.data.hue or 0, self.coordinator.data.saturation or 0)

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return self.coordinator.data.on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        try:
            await self.client.light(on=False)
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while updating the Elgato Light"
            ) from error
        finally:
            await self.coordinator.async_refresh()

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
            and self.supported_color_modes
            and ColorMode.HS in self.supported_color_modes
            and self.color_mode == ColorMode.COLOR_TEMP
        ):
            temperature = self.color_temp

        try:
            await self.client.light(
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
            await self.client.identify()
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while identifying the Elgato Light"
            ) from error
