"""Light platform for the fan LED."""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .api import (
    COMMAND_BRIGHTNESS,
    COMMAND_LED,
    COMMAND_LIGHT_MODE,
    DEVICE_TYPE_FAN,
    AtombergDevice,
)
from .const import LED_BRIGHTNESS_RANGE, LIGHT_MODES
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg fan lights."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergLight(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_FAN)
        if COMMAND_LED in device.supported_commands
    )


class AtombergLight(AtombergEntity, LightEntity):
    """Representation of the LED on an Atomberg fan."""

    _attr_translation_key = "led"

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, device, "led")
        commands = device.supported_commands
        self._has_brightness = COMMAND_BRIGHTNESS in commands
        self._attr_supported_color_modes = {
            ColorMode.BRIGHTNESS if self._has_brightness else ColorMode.ONOFF
        }
        self._attr_color_mode = next(iter(self._attr_supported_color_modes))
        if COMMAND_LIGHT_MODE in commands:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = LIGHT_MODES

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the LED is on."""
        return self.device_state[COMMAND_LED]

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness."""
        value = self.device_state[COMMAND_BRIGHTNESS]
        if not self._has_brightness or value is None:
            return None
        return value_to_brightness(LED_BRIGHTNESS_RANGE, value)

    @property
    @override
    def effect(self) -> str | None:
        """Return the light mode."""
        if COMMAND_LIGHT_MODE not in self.device.supported_commands:
            return None
        return self.device_state[COMMAND_LIGHT_MODE]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED on, optionally changing brightness or light mode."""
        command: dict[str, Any] = {}
        if ATTR_BRIGHTNESS in kwargs:
            command[COMMAND_BRIGHTNESS] = round(
                brightness_to_value(LED_BRIGHTNESS_RANGE, kwargs[ATTR_BRIGHTNESS])
            )
        if ATTR_EFFECT in kwargs:
            command[COMMAND_LIGHT_MODE] = kwargs[ATTR_EFFECT]
        if not command:
            command[COMMAND_LED] = True
        await self._async_send(command, {**command, COMMAND_LED: True})

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED off."""
        await self._async_send({COMMAND_LED: False}, {COMMAND_LED: False})
