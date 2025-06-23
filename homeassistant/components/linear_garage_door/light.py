"""Linear garage door light."""

from typing import Any

from linear_garage_door import Linear

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LinearUpdateCoordinator
from .entity import LinearEntity

SUPPORTED_SUBDEVICES = ["Light"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linear Garage Door cover."""
    coordinator: LinearUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    data = coordinator.data

    async_add_entities(
        LinearLightEntity(
            device_id=device_id,
            device_name=data[device_id].name,
            sub_device_id=subdev,
            coordinator=coordinator,
        )
        for device_id in data
        for subdev in data[device_id].subdevices
        if subdev in SUPPORTED_SUBDEVICES
    )


class LinearLightEntity(LinearEntity, LightEntity):
    """Light for Linear devices."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "light"

    @property
    def is_on(self) -> bool:
        """Return if the light is on or not."""
        return bool(self.sub_device["On_B"] == "true")

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return round(int(self.sub_device["On_P"]) / 100 * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        async def _turn_on(linear: Linear) -> None:
            """Turn on the light."""
            if not kwargs:
                await linear.operate_device(self._device_id, self._sub_device_id, "On")
            elif ATTR_BRIGHTNESS in kwargs:
                brightness = round((kwargs[ATTR_BRIGHTNESS] / 255) * 100)
                await linear.operate_device(
                    self._device_id, self._sub_device_id, f"DimPercent:{brightness}"
                )

        await self.coordinator.execute(_turn_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        await self.coordinator.execute(
            lambda linear: linear.operate_device(
                self._device_id, self._sub_device_id, "Off"
            )
        )
