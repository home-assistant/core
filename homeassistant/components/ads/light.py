"""Support for ADS light sources."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import ads
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ADS_FACTOR,
    CONF_ADS_TYPE,
    CONF_ADS_VAR,
    CONF_ADS_VAR_BRIGHTNESS,
    DATA_ADS,
    STATE_KEY_BRIGHTNESS,
    STATE_KEY_STATE,
    AdsEntity,
)

DEFAULT_NAME = "ADS Light"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_ADS_VAR_BRIGHTNESS): cv.string,
        vol.Optional(CONF_ADS_TYPE, default=ads.ADSTYPE_UINT): vol.In(
            [
                ads.ADSTYPE_INT,
                ads.ADSTYPE_UINT,
                ads.ADSTYPE_BYTE,
                ads.ADSTYPE_DINT,
                ads.ADSTYPE_UDINT,
            ]
        ),
        vol.Optional(CONF_ADS_FACTOR, default=1): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    ads_var_enable = config[CONF_ADS_VAR]
    ads_var_brightness = config.get(CONF_ADS_VAR_BRIGHTNESS)
    ads_type = config.get(CONF_ADS_TYPE)
    ads_factor = config.get(CONF_ADS_FACTOR)
    name = config[CONF_NAME]

    add_entities(
        [
            AdsLight(
                ads_hub, ads_var_enable, ads_var_brightness, ads_type, ads_factor, name
            )
        ]
    )


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(
        self, ads_hub, ads_var_enable, ads_var_brightness, ads_type, ads_factor, name
    ):
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)
        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._ads_var_brightness = ads_var_brightness
        self._ads_type = ads_type
        self._ads_factor = ads_factor
        if ads_var_brightness is not None:
            self._attr_supported_features = SUPPORT_BRIGHTNESS

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, self._ads_hub.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None:
            await self.async_initialize_device(
                self._ads_var_brightness,
                self._ads_hub.ADS_TYPEMAP[self._ads_type],
                STATE_KEY_BRIGHTNESS,
            )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0..255)."""
        return self._state_dict[STATE_KEY_BRIGHTNESS] / self._ads_factor

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs):
        """Turn the light on or set a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        self._ads_hub.write_by_name(self._ads_var, True, self._ads_hub.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None and brightness is not None:
            self._ads_hub.write_by_name(
                self._ads_var_brightness,
                brightness * self._ads_factor,
                self._ads_hub.ADS_TYPEMAP[self._ads_type],
            )

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, self._ads_hub.PLCTYPE_BOOL)
