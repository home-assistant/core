"""Provides a light for Home Connect."""

from dataclasses import dataclass
import logging
from typing import Any, cast

from aiohomeconnect.model import Event, EventKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .const import (
    BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
    DOMAIN,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
)
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HomeConnectLightEntityDescription(LightEntityDescription):
    """Light entity description."""

    brightness_key: SettingKey | None = None
    color_key: SettingKey | None = None
    enable_custom_color_value_key: str | None = None
    custom_color_key: SettingKey | None = None
    brightness_scale: tuple[float, float] = (0.0, 100.0)


LIGHTS: tuple[HomeConnectLightEntityDescription, ...] = (
    HomeConnectLightEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_LIGHT_INTERNAL_POWER,
        brightness_key=SettingKey.REFRIGERATION_COMMON_LIGHT_INTERNAL_BRIGHTNESS,
        brightness_scale=(1.0, 100.0),
        translation_key="internal_light",
    ),
    HomeConnectLightEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_LIGHT_EXTERNAL_POWER,
        brightness_key=SettingKey.REFRIGERATION_COMMON_LIGHT_EXTERNAL_BRIGHTNESS,
        brightness_scale=(1.0, 100.0),
        translation_key="external_light",
    ),
    HomeConnectLightEntityDescription(
        key=SettingKey.COOKING_COMMON_LIGHTING,
        brightness_key=SettingKey.COOKING_COMMON_LIGHTING_BRIGHTNESS,
        brightness_scale=(10.0, 100.0),
        translation_key="cooking_lighting",
    ),
    HomeConnectLightEntityDescription(
        key=SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED,
        brightness_key=SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS,
        color_key=SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR,
        enable_custom_color_value_key=BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
        custom_color_key=SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR,
        brightness_scale=(10.0, 100.0),
        translation_key="ambient_light",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect light."""

    async_add_entities(
        [
            HomeConnectLight(entry.runtime_data, appliance, description)
            for description in LIGHTS
            for appliance in entry.runtime_data.data.values()
            if description.key in appliance.settings
        ],
        True,
    )


class HomeConnectLight(HomeConnectEntity, LightEntity):
    """Light for Home Connect."""

    entity_description: LightEntityDescription

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectLightEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, appliance, desc)

        def get_setting_key_if_setting_exists(
            setting_key: SettingKey | None,
        ) -> SettingKey | None:
            if setting_key and setting_key in appliance.settings:
                return setting_key
            return None

        self._brightness_key = get_setting_key_if_setting_exists(desc.brightness_key)
        self._custom_color_key = get_setting_key_if_setting_exists(
            desc.custom_color_key
        )
        self._color_key = get_setting_key_if_setting_exists(desc.color_key)
        self._enable_custom_color_value_key = desc.enable_custom_color_value_key
        self._custom_color_key = get_setting_key_if_setting_exists(
            desc.custom_color_key
        )
        self._brightness_scale = desc.brightness_scale

        match (self._brightness_key, self._custom_color_key):
            case (None, None):
                self._attr_color_mode = ColorMode.ONOFF
                self._attr_supported_color_modes = {ColorMode.ONOFF}
            case (_, None):
                self._attr_color_mode = ColorMode.BRIGHTNESS
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            case (_, _):
                self._attr_color_mode = ColorMode.HS
                self._attr_supported_color_modes = {ColorMode.HS, ColorMode.RGB}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the light on, change brightness, change color."""
        _LOGGER.debug("Switching light on for: %s", self.name)
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=True,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_light",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                },
            ) from err
        if self._color_key and self._custom_color_key:
            if (
                ATTR_RGB_COLOR in kwargs or ATTR_HS_COLOR in kwargs
            ) and self._enable_custom_color_value_key:
                try:
                    await self.coordinator.client.set_setting(
                        self.appliance.info.ha_id,
                        setting_key=self._color_key,
                        value=self._enable_custom_color_value_key,
                    )
                except HomeConnectError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="select_light_custom_color",
                        translation_placeholders={
                            **get_dict_from_home_connect_error(err),
                            SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                        },
                    ) from err

            if ATTR_RGB_COLOR in kwargs:
                hex_val = color_util.color_rgb_to_hex(*kwargs[ATTR_RGB_COLOR])
                try:
                    await self.coordinator.client.set_setting(
                        self.appliance.info.ha_id,
                        setting_key=self._custom_color_key,
                        value=f"#{hex_val}",
                    )
                except HomeConnectError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="set_light_color",
                        translation_placeholders={
                            **get_dict_from_home_connect_error(err),
                            SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                        },
                    ) from err
                return
            if (self._attr_brightness is not None or ATTR_BRIGHTNESS in kwargs) and (
                self._attr_hs_color is not None or ATTR_HS_COLOR in kwargs
            ):
                brightness = round(
                    color_util.brightness_to_value(
                        self._brightness_scale,
                        kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness),
                    )
                )

                hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)

                rgb = color_util.color_hsv_to_RGB(hs_color[0], hs_color[1], brightness)
                hex_val = color_util.color_rgb_to_hex(*rgb)
                try:
                    await self.coordinator.client.set_setting(
                        self.appliance.info.ha_id,
                        setting_key=self._custom_color_key,
                        value=f"#{hex_val}",
                    )
                except HomeConnectError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="set_light_color",
                        translation_placeholders={
                            **get_dict_from_home_connect_error(err),
                            SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                        },
                    ) from err
                return

        if self._brightness_key and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug(
                "Changing brightness for: %s, to: %s",
                self.name,
                kwargs[ATTR_BRIGHTNESS],
            )
            brightness = round(
                color_util.brightness_to_value(
                    self._brightness_scale, kwargs[ATTR_BRIGHTNESS]
                )
            )
            try:
                await self.coordinator.client.set_setting(
                    self.appliance.info.ha_id,
                    setting_key=self._brightness_key,
                    value=brightness,
                )
            except HomeConnectError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_light_brightness",
                    translation_placeholders={
                        **get_dict_from_home_connect_error(err),
                        SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    },
                ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
        _LOGGER.debug("Switching light off for: %s", self.name)
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=False,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_light",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                },
            ) from err

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        if self._brightness_key:
            self.coordinator.add_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._brightness_key),
                self._async_event_update_brightness_listener,
            )
        if self._color_key and self._custom_color_key:
            self.coordinator.add_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._color_key),
                self._async_event_update_color_listener,
            )
            self.coordinator.add_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._custom_color_key),
                self._async_event_update_custom_color_listener,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister listener."""
        await super().async_will_remove_from_hass()
        if self._brightness_key:
            self.coordinator.delete_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._brightness_key),
                self._async_event_update_brightness_listener,
            )
        if self._color_key and self._custom_color_key:
            self.coordinator.delete_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._color_key),
                self._async_event_update_color_listener,
            )
            self.coordinator.delete_home_appliances_event_listener(
                self.appliance.info.ha_id,
                EventKey(self._custom_color_key),
                self._async_event_update_custom_color_listener,
            )

    async def _async_event_update_listener(self, event: Event) -> None:
        self._attr_is_on = cast(bool, event.value)
        self.async_write_ha_state()

    async def _async_event_update_brightness_listener(self, event: Event) -> None:
        self.update_brightness(cast(float, event.value))
        self.async_write_ha_state()

    async def _async_event_update_color_listener(self, event: Event) -> None:
        if event.value != self._enable_custom_color_value_key:
            self._attr_rgb_color = None
            self._attr_hs_color = None
            self.async_write_ha_state()

    async def _async_event_update_custom_color_listener(self, event: Event) -> None:
        self.update_color(cast(str, event.value))
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the light's status."""
        self._attr_is_on = self.appliance.settings[SettingKey(self.bsh_key)].value

        _LOGGER.debug("Updated, new light state: %s", self._attr_is_on)
        if self._brightness_key:
            brightness = cast(
                float, self.appliance.settings[self._brightness_key].value
            )
            self.update_brightness(brightness)
        if self._color_key and self._custom_color_key:
            color = cast(str, self.appliance.settings[self._color_key].value)
            if color != self._enable_custom_color_value_key:
                self._attr_rgb_color = None
                self._attr_hs_color = None
            else:
                custom_color = cast(
                    str, self.appliance.settings[self._custom_color_key].value
                )
                self.update_color(custom_color)

    def update_brightness(self, brightness: float) -> None:
        """Update brightness value of the light."""
        self._attr_brightness = color_util.value_to_brightness(
            self._brightness_scale, brightness
        )
        _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)

    def update_color(self, color: str) -> None:
        """Update color value of the light."""
        color_value = color[1:]
        rgb = color_util.rgb_hex_to_rgb_list(color_value)
        self._attr_rgb_color = (rgb[0], rgb[1], rgb[2])
        hsv = color_util.color_RGB_to_hsv(*rgb)
        self._attr_hs_color = (hsv[0], hsv[1])
        self._attr_brightness = color_util.value_to_brightness(
            self._brightness_scale, hsv[2]
        )
        _LOGGER.debug(
            "Updated, new color (%s) and new brightness (%s) ",
            color_value,
            self._attr_brightness,
        )
