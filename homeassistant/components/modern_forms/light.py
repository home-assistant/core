"""Support for Modern Forms Fan lights."""

from typing import Any, override

from aiomodernforms.const import LIGHT_POWER_OFF, LIGHT_POWER_ON
from aiomodernforms.models import Light
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import modernforms_exception_handler
from .const import (
    ATTR_SLEEP_TIME,
    CLEAR_TIMER,
    DOMAIN,
    OPT_BRIGHTNESS,
    OPT_COLOR_TEMP_KELVIN,
    OPT_ON,
    SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
    SERVICE_SET_LIGHT_SLEEP_TIMER,
)
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity, strip_device_name_prefix

BRIGHTNESS_RANGE = (1, 255)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ModernFormsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Modern Forms platform from config entry."""

    coordinator = config_entry.runtime_data

    # if no light unit installed no light entity
    if not coordinator.data.info.light_type:
        return

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_LIGHT_SLEEP_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
        },
        "async_set_light_sleep_timer",
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
        None,
        "async_clear_light_sleep_timer",
    )

    async_add_entities(
        ModernFormsLightEntity(
            entry_id=config_entry.entry_id,
            coordinator=coordinator,
            light_address=light.address,
        )
        for light in coordinator.data.state.light_fixtures
    )


class ModernFormsLightEntity(ModernFormsDeviceEntity, LightEntity):
    """Defines a Modern Forms light."""

    _attr_translation_key = "light"

    def __init__(
        self,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        light_address: int | None,
    ) -> None:
        """Initialize Modern Forms light."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._address = light_address
        mac_address = self.coordinator.data.info.mac_address

        if light_address is None:
            self._attr_unique_id = mac_address
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            # Real Gen4 fixtures are named by the user, so the device-name
            # prefix strip below is per-device data rather than static.
            self._attr_unique_id = f"{mac_address}_{light_address}"
            fixture = next(
                light
                for light in coordinator.data.state.light_fixtures
                if light.address == light_address
            )
            self._attr_name = strip_device_name_prefix(
                self.coordinator.data.info.device_name, fixture.name
            )

            if (
                fixture.min_color_temp_kelvin is not None
                and fixture.max_color_temp_kelvin is not None
            ):
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
                self._attr_min_color_temp_kelvin = fixture.min_color_temp_kelvin
                self._attr_max_color_temp_kelvin = fixture.max_color_temp_kelvin
            else:
                self._attr_color_mode = ColorMode.BRIGHTNESS
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def _light(self) -> Light | None:
        """Return this entity's current fixture data, if it still exists."""
        for light in self.coordinator.data.state.light_fixtures:
            if light.address == self._address:
                return light
        return None

    @property
    @override
    def available(self) -> bool:
        """Return True if the fixture this entity represents still exists."""
        return super().available and self._light is not None

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        if self._light is None:
            return None
        return round(
            percentage_to_ranged_value(BRIGHTNESS_RANGE, self._light.brightness)
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the light."""
        return self._light is not None and bool(self._light.on)

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature of this light in Kelvin."""
        return self._light.color_temp_kelvin if self._light is not None else None

    @modernforms_exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_control_light(on=LIGHT_POWER_OFF)

    @modernforms_exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: dict[str, Any] = {OPT_ON: LIGHT_POWER_ON}

        if ATTR_BRIGHTNESS in kwargs:
            data[OPT_BRIGHTNESS] = ranged_value_to_percentage(
                BRIGHTNESS_RANGE, kwargs[ATTR_BRIGHTNESS]
            )
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            data[OPT_COLOR_TEMP_KELVIN] = kwargs[ATTR_COLOR_TEMP_KELVIN]

        await self._async_control_light(**data)

    @modernforms_exception_handler
    async def async_set_light_sleep_timer(
        self,
        sleep_time: int,
    ) -> None:
        """Set a Modern Forms light sleep timer."""
        if not self.coordinator.data.has_sleep_timer():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sleep_timer_not_supported",
            )
        await self._async_control_light(sleep=sleep_time * 60)

    @modernforms_exception_handler
    async def async_clear_light_sleep_timer(
        self,
    ) -> None:
        """Clear a Modern Forms light sleep timer."""
        if not self.coordinator.data.has_sleep_timer():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sleep_timer_not_supported",
            )
        await self._async_control_light(sleep=CLEAR_TIMER)

    async def _async_control_light(self, **kwargs: Any) -> None:
        """Send a control command to this entity's fixture."""
        if self._address is None:
            await self.coordinator.modern_forms.light(**kwargs)
        else:
            await self.coordinator.modern_forms.light_fixture(self._address, **kwargs)
