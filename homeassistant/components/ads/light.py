"""Support for ADS light sources."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_LIGHTS, CONF_NAME

from . import (
    CONF_ADS_VAR,
    CONF_ADS_VAR_BRIGHTNESS,
    DATA_ADS,
    STATE_KEY_BRIGHTNESS,
    STATE_KEY_STATE,
    AdsEntity,
)


def setup_platform(hass, config, add_entities, discovery_info):
    """Set up the light platform for ADS."""
    entities = []

    if discovery_info is None:  # pragma: no cover
        return

    ads_hub = hass.data.get(DATA_ADS)

    for entry in discovery_info[CONF_LIGHTS]:
        ads_var_enable = entry.get(CONF_ADS_VAR)
        ads_var_brightness = entry.get(CONF_ADS_VAR_BRIGHTNESS)
        name = entry.get(CONF_NAME)
        entities.append(AdsLight(ads_hub, ads_var_enable, ads_var_brightness, name))

    add_entities(entities)


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(self, ads_hub, ads_var_enable, ads_var_brightness, name):
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)
        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._ads_var_brightness = ads_var_brightness
        if ads_var_brightness is not None:
            self._attr_supported_features = SUPPORT_BRIGHTNESS

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
    def brightness(self) -> int | None:
        """Return the brightness of the light (0..255)."""
        return self._state_dict[STATE_KEY_BRIGHTNESS]

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
                self._ads_var_brightness, brightness, self._ads_hub.PLCTYPE_UINT
            )

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, self._ads_hub.PLCTYPE_BOOL)
