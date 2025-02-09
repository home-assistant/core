"""Handle the Gryf Smart light platform functionality."""

from typing import Any

from pygryfsmart.device import _GryfDevice, _GryfOutput, _GryfPwm

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_API, CONF_DEVICES, CONF_ID, CONF_NAME, PLATFORM_PWM
from .entity import GryfBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow for Light platform."""
    lights = []
    pwm = []

    for conf in config_entry.data[CONF_DEVICES]:
        if conf.get(CONF_TYPE) == Platform.LIGHT:
            device = _GryfOutput(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                config_entry.runtime_data[CONF_API],
            )
            lights.append(GryfLight(device, config_entry))
        elif conf.get(CONF_TYPE) == PLATFORM_PWM:
            device = _GryfPwm(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                config_entry.runtime_data[CONF_API],
            )
            pwm.append(GryfPwm(device, config_entry))

    async_add_entities(lights)
    async_add_entities(pwm)


class LightBase(LightEntity):
    """Gryf Light entity base."""

    _is_on = False
    _device: _GryfDevice
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self):
        """Return is on."""

        return self._is_on

    async def async_update(self, is_on):
        """Update state."""

        self._is_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""

        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""

        await self._device.turn_off()


class GryfLight(GryfBaseEntity, LightBase):
    """Gryf Smart config flow Light class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Init the Gryf Light."""

        self._config_entry = config_entry
        super().__init__(config_entry, device)
        self._device.subscribe(self.async_update)


class GryfPwmBase(LightEntity):
    """Gryf Pwm entity base."""

    _is_on = False
    _brightness = 0
    _device: _GryfDevice
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int | None:
        """The brightness property."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """The is_on property."""

        return self._is_on

    async def async_update(self, brightness):
        """Update state."""

        self._is_on = bool(brightness)
        self._brightness = brightness
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn pwm on."""
        brightness = kwargs.get("brightness")
        if brightness is not None:
            percentage_brightness = int((brightness / 255) * 100)
            await self._device.set_level(percentage_brightness)

        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn pwm off."""

        await self._device.turn_off()


class GryfPwm(GryfBaseEntity, GryfPwmBase):
    """Gryf Smart config flow Light class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Init the Gryf Light."""

        self._config_entry = config_entry
        super().__init__(config_entry, device)
        self._device.subscribe(self.async_update)
