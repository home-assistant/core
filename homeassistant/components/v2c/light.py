"""Light platform for V2C EVSE LEDs."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pytrydan import Trydan, TrydanData

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity

LED_ON_VALUE = 100
LED_OFF_VALUE = 0
BRIGHTNESS_SCALE = (LED_OFF_VALUE, LED_ON_VALUE)


@dataclass(frozen=True, kw_only=True)
class V2CLightEntityDescription(LightEntityDescription):
    """Describes V2C EVSE light entity."""

    supports_brightness: bool = False
    value_fn: Callable[[TrydanData], int | None]
    update_fn: Callable[[Trydan, int], Coroutine[Any, Any, None]]


TRYDAN_LIGHTS = (
    V2CLightEntityDescription(
        key="light_led",
        translation_key="light_led",
        entity_registry_enabled_default=False,
        value_fn=lambda evse_data: evse_data.light_led,
        update_fn=lambda evse, value: evse.light_led(value),
    ),
    V2CLightEntityDescription(
        key="logo_led",
        translation_key="logo_led",
        supports_brightness=True,
        value_fn=lambda evse_data: evse_data.logo_led,
        update_fn=lambda evse, value: evse.logo_led(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up V2C Trydan light platform."""
    coordinator = config_entry.runtime_data
    data = coordinator.data
    assert data is not None

    async_add_entities(
        V2CLightEntity(
            coordinator,
            description,
            config_entry.entry_id,
        )
        for description in TRYDAN_LIGHTS
        if description.value_fn(data) is not None
    )


class V2CLightEntity(V2CBaseEntity, LightEntity):
    """Representation of V2C EVSE LED light entity."""

    entity_description: V2CLightEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CLightEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C light entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if description.supports_brightness else ColorMode.ONOFF
        )
        self._attr_supported_color_modes = {self._attr_color_mode}

    @property
    def brightness(self) -> int | None:
        """Return the light brightness."""
        if not self.entity_description.supports_brightness:
            return None
        value = self.entity_description.value_fn(self.data)
        if value is None:
            return None
        return value_to_brightness(BRIGHTNESS_SCALE, value)

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        value = self.entity_description.value_fn(self.data)
        if value is None:
            return None
        return value > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LED."""
        value = LED_ON_VALUE
        if self.entity_description.supports_brightness:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
            value = round(brightness_to_value(BRIGHTNESS_SCALE, brightness))
            if brightness:
                value = max(value, 1)
        await self.entity_description.update_fn(self.coordinator.evse, value)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LED."""
        await self.entity_description.update_fn(self.coordinator.evse, LED_OFF_VALUE)
        await self.coordinator.async_request_refresh()
