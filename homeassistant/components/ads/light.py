"""Support for ADS light sources."""
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import (
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
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the light platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    ads_var_enable = config[CONF_ADS_VAR]
    ads_var_brightness = config.get(CONF_ADS_VAR_BRIGHTNESS)
    name = config[CONF_NAME]

    add_entities([AdsLight(ads_hub, ads_var_enable, ads_var_brightness, name)])


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(self, ads_hub, ads_var_enable, ads_var_brightness, name):
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)
        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._ads_var_brightness = ads_var_brightness

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, self._ads_hub.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None:
            await self.async_initialize_device(
                self._ads_var_brightness,
                self._ads_hub.PLCTYPE_UINT,
                STATE_KEY_BRIGHTNESS,
            )

    @property
    def brightness(self):
        """Return the brightness of the light (0..255)."""
        return self._state_dict[STATE_KEY_BRIGHTNESS]

    @property
    def supported_features(self):
        """Flag supported features."""
        support = 0
        if self._ads_var_brightness is not None:
            support = SUPPORT_BRIGHTNESS
        return support

    @property
    def is_on(self):
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs):
        """Turn the light on or set a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        self._ads_hub.write_by_name(self._ads_var, True, self._ads_hub.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None and brightness is not None:
            self._ads_hub.write_by_name(
                self._ads_var_brightness, brightness, self._ads_hub.PLCTYPE_UINT
            )

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, self._ads_hub.PLCTYPE_BOOL)
