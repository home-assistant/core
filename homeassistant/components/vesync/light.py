"""Support for VeSync bulbs, wall dimmers, and humidifier night lights."""

import logging
from typing import Any, override

from pyvesync.base_devices.bulb_base import VeSyncBulb
from pyvesync.base_devices.humidifier_base import VeSyncHumidifier
from pyvesync.base_devices.switch_base import VeSyncSwitch
from pyvesync.const import NightlightStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from .const import DOMAIN, VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)
MAX_MIREDS = 370  # 1,000,000 divided by 2700 Kelvin = 370 Mireds
MIN_MIREDS = 153  # 1,000,000 divided by 6500 Kelvin = 153 Mireds
RGB_NIGHTLIGHT_BRIGHTNESS_RANGE = (40, 100)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBulb | VeSyncSwitch | VeSyncHumidifier]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices.bulbs
        + config_entry.runtime_data.manager.devices.switches
        + config_entry.runtime_data.manager.devices.humidifiers,
        async_add_entities,
        coordinator,
    )


@callback
def _setup_entities(
    devices: list[VeSyncBulb | VeSyncSwitch | VeSyncHumidifier],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Check if device is a light and add entity."""
    entities: list[LightEntity] = []
    for dev in devices:
        if isinstance(dev, VeSyncBulb):
            if dev.supports_color_temp:
                entities.append(VeSyncTunableWhiteLightHA(dev, coordinator))
            elif dev.supports_brightness:
                entities.append(VeSyncDimmableLightHA(dev, coordinator))
        elif isinstance(dev, VeSyncSwitch) and dev.supports_dimmable:
            entities.append(VeSyncDimmableLightHA(dev, coordinator))
        elif isinstance(dev, VeSyncHumidifier) and dev.supports_rgb_nightlight:
            entities.append(VeSyncHumidifierRGBNightLightHA(dev, coordinator))

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseLightHA(VeSyncBaseEntity[VeSyncSwitch | VeSyncBulb], LightEntity):
    """Base class for VeSync Light Devices Representations."""

    device: VeSyncBulb | VeSyncSwitch
    _attr_name = None

    @property
    @override
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.state.device_status == "on"

    @property
    @override
    def brightness(self) -> int:
        """Get light brightness."""
        if self.device.state.brightness is None:
            _LOGGER.debug(
                "VeSync - received unexpected 'brightness'"
                " value from pyvesync api of None"
            )
            return 0

        # convert percent brightness to ha expected range
        return round((max(1, self.device.state.brightness) / 100) * 255)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        attribute_adjustment_only = False
        # set white temperature
        if (
            self.color_mode == ColorMode.COLOR_TEMP
            and ATTR_COLOR_TEMP_KELVIN in kwargs
            and hasattr(self.device, "set_color_temp")
        ):
            # get white temperature from HA data
            color_temp = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_COLOR_TEMP_KELVIN]
            )
            # ensure value between min-max supported Mireds
            color_temp = max(MIN_MIREDS, min(color_temp, MAX_MIREDS))
            # convert Mireds to Percent value that api expects
            color_temp = round(
                ((color_temp - MIN_MIREDS) / (MAX_MIREDS - MIN_MIREDS)) * 100
            )
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 0-100
            color_temp = max(0, min(color_temp, 100))
            # call pyvesync library api method to set color_temp
            await self.device.set_color_temp(color_temp)
            # flag attribute_adjustment_only, so it doesn't
            # turn_on the device redundantly
            attribute_adjustment_only = True
        # set brightness level
        if (
            self.color_mode in (ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP)
            and ATTR_BRIGHTNESS in kwargs
        ):
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # ensure value between 1-255
            brightness = max(1, min(brightness, 255))
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # ensure value between 1-100
            brightness = max(1, min(brightness, 100))
            # call pyvesync library api method to set brightness
            await self.device.set_brightness(brightness)
            # flag attribute_adjustment_only, so it doesn't
            # turn_on the device redundantly
            attribute_adjustment_only = True
        # check flag if should skip sending the turn_on command
        if attribute_adjustment_only:
            return
        # send turn_on command to pyvesync api
        await self.device.turn_on()
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.device.turn_off()
        self.async_write_ha_state()


class VeSyncDimmableLightHA(VeSyncBaseLightHA, LightEntity):
    """Representation of a VeSync dimmable light device."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}


class VeSyncTunableWhiteLightHA(VeSyncBaseLightHA, LightEntity):
    """Representation of a VeSync Tunable White Light device."""

    device: VeSyncBulb
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = 2700  # 370 Mireds
    _attr_max_color_temp_kelvin = 6500  # 153 Mireds
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if hasattr(self.device.state, "color_temp") is False:
            return None

        # pyvesync v3 provides BulbState.color_temp_kelvin()
        # - possible to use that instead?
        if self.device.state.color_temp is None:
            _LOGGER.debug(
                "VeSync - received unexpected 'color_temp'"
                " value from pyvesync api of None"
            )
            return 0

        # flip cold/warm
        color_temp_value = 100 - self.device.state.color_temp
        # ensure value between 0-100
        color_temp_value = max(0, min(color_temp_value, 100))
        # convert percent value to Mireds
        color_temp_value = round(
            MIN_MIREDS + ((MAX_MIREDS - MIN_MIREDS) / 100 * color_temp_value)
        )
        # ensure value between minimum and maximum Mireds
        return color_util.color_temperature_mired_to_kelvin(
            max(MIN_MIREDS, min(color_temp_value, MAX_MIREDS))
        )


class VeSyncHumidifierRGBNightLightHA(VeSyncBaseEntity[VeSyncHumidifier], LightEntity):
    """Representation of a VeSync humidifier RGB night light."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_translation_key = "nightlight"

    def __init__(
        self, device: VeSyncHumidifier, coordinator: VeSyncDataCoordinator
    ) -> None:
        """Initialize the night light."""
        super().__init__(device, coordinator)
        self._attr_unique_id = f"{self.base_unique_id}-nightlight"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the night light is on."""
        return self.device.state.rgb_nightlight_status == NightlightStatus.ON

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of the night light."""
        if (brightness := self.device.state.rgb_nightlight_brightness) is None:
            return None
        return color_util.value_to_brightness(
            RGB_NIGHTLIGHT_BRIGHTNESS_RANGE, brightness
        )

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the night light."""
        red = self.device.state.rgb_nightlight_red
        green = self.device.state.rgb_nightlight_green
        blue = self.device.state.rgb_nightlight_blue
        if red is None or green is None or blue is None:
            return None
        return red, green, blue

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the night light on."""
        brightness = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = max(
                RGB_NIGHTLIGHT_BRIGHTNESS_RANGE[0],
                round(
                    color_util.brightness_to_value(
                        RGB_NIGHTLIGHT_BRIGHTNESS_RANGE, kwargs[ATTR_BRIGHTNESS]
                    )
                ),
            )
        red, green, blue = kwargs.get(ATTR_RGB_COLOR, (None, None, None))
        if not await self.device.set_rgb_nightlight(
            power=True, brightness=brightness, red=red, green=green, blue=blue
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="nightlight_command_failed"
            )
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the night light off."""
        if not await self.device.set_rgb_nightlight(power=False):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="nightlight_command_failed"
            )
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the night light state is available."""
        return super().available and self.device.state.rgb_nightlight_status is not None
