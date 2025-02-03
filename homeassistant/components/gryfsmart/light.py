"""Handle the Gryf Smart light platform functionality."""

from typing import Any

from pygryfsmart.device import _GryfDevice, _GryfOutput, _GryfPwm

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_API, CONF_DEVICES, CONF_ID, CONF_NAME, CONF_PWM, DOMAIN
from .entity import GryfConfigFlowEntity, GryfYamlEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the Light platform."""

    lights = []
    pwm = []

    for conf in hass.data[DOMAIN].get(Platform.LIGHT, {}):
        device = _GryfOutput(
            conf.get(CONF_NAME),
            conf.get(CONF_ID) // 10,
            conf.get(CONF_ID) % 10,
            hass.data[DOMAIN][CONF_API],
        )
        lights.append(GryfYamlLight(device))

    for conf in hass.data[DOMAIN].get(CONF_PWM, {}):
        device = _GryfPwm(
            conf.get(CONF_NAME),
            conf.get(CONF_ID) // 10,
            conf.get(CONF_ID) % 10,
            hass.data[DOMAIN][CONF_API],
        )
        pwm.append(GryfYamlPwm(device))

    async_add_entities(lights)
    async_add_entities(pwm)


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
            lights.append(GryfConfigFlowLight(device, config_entry))
        elif conf.get(CONF_TYPE) == CONF_PWM:
            device = _GryfPwm(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                config_entry.runtime_data[CONF_API],
            )
            pwm.append(GryfConfigFlowPwm(device, config_entry))

    async_add_entities(lights)
    async_add_entities(pwm)


class GryfLightBase(LightEntity):
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


class GryfConfigFlowLight(GryfConfigFlowEntity, GryfLightBase):
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


class GryfYamlLight(GryfYamlEntity, GryfLightBase):
    """Gryf Smart Yaml Light class."""

    def __init__(self, device: _GryfDevice) -> None:
        """Init the Gryf Light."""

        super().__init__(device)
        device.subscribe(self.async_update)


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


class GryfConfigFlowPwm(GryfConfigFlowEntity, GryfPwmBase):
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


class GryfYamlPwm(GryfYamlEntity, GryfPwmBase):
    """Gryf Smart Yaml Light class."""

    def __init__(self, device: _GryfDevice) -> None:
        """Init the Gryf Light."""

        super().__init__(device)
        device.subscribe(self.async_update)
