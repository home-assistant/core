"""Provides a light for Home Connect."""

from dataclasses import dataclass
import logging
from typing import Any, cast

from aiohomeconnect.model import EventKey, SettingKey
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from .common import setup_home_connect_entry
from .const import BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR, DOMAIN
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


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


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        HomeConnectLight(entry.runtime_data, appliance, description)
        for description in LIGHTS
        if description.key in appliance.settings
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect light."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
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

        super().__init__(coordinator, appliance, desc)

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
                    "entity_id": self.entity_id,
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
                            "entity_id": self.entity_id,
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
                            "entity_id": self.entity_id,
                        },
                    ) from err
                return
            if (self._attr_brightness is not None or ATTR_BRIGHTNESS in kwargs) and (
                self._attr_hs_color is not None or ATTR_HS_COLOR in kwargs
            ):
                brightness = round(
                    color_util.brightness_to_value(
                        self._brightness_scale,
                        cast(int, kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)),
                    )
                )

                hs_color = cast(
                    tuple[float, float], kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)
                )

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
                            "entity_id": self.entity_id,
                        },
                    ) from err
                return

        if self._brightness_key and ATTR_BRIGHTNESS in kwargs:
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
                        "entity_id": self.entity_id,
                    },
                ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
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
                    "entity_id": self.entity_id,
                },
            ) from err

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        keys_to_listen = []
        if self._brightness_key:
            keys_to_listen.append(self._brightness_key)
        if self._color_key and self._custom_color_key:
            keys_to_listen.extend([self._color_key, self._custom_color_key])
        for key in keys_to_listen:
            self.async_on_remove(
                self.coordinator.async_add_listener(
                    self._handle_coordinator_update,
                    (
                        self.appliance.info.ha_id,
                        EventKey(key),
                    ),
                )
            )

    def update_native_value(self) -> None:
        """Update the light's status."""
        self._attr_is_on = self.appliance.settings[SettingKey(self.bsh_key)].value

        if self._brightness_key:
            brightness = cast(
                float, self.appliance.settings[self._brightness_key].value
            )
            self._attr_brightness = color_util.value_to_brightness(
                self._brightness_scale, brightness
            )
            _LOGGER.debug(
                "Updated %s, new brightness: %s", self.entity_id, self._attr_brightness
            )
        if self._color_key and self._custom_color_key:
            color = cast(str, self.appliance.settings[self._color_key].value)
            if color != self._enable_custom_color_value_key:
                self._attr_rgb_color = None
                self._attr_hs_color = None
            else:
                custom_color = cast(
                    str, self.appliance.settings[self._custom_color_key].value
                )
                color_value = custom_color[1:]
                rgb = color_util.rgb_hex_to_rgb_list(color_value)
                self._attr_rgb_color = (rgb[0], rgb[1], rgb[2])
                hsv = color_util.color_RGB_to_hsv(*rgb)
                self._attr_hs_color = (hsv[0], hsv[1])
                self._attr_brightness = color_util.value_to_brightness(
                    self._brightness_scale, hsv[2]
                )
                _LOGGER.debug(
                    "Updated %s, new color (%s) and new brightness (%s) ",
                    self.entity_id,
                    color_value,
                    self._attr_brightness,
                )
