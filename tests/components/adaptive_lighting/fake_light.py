"""Fake light entity bases on 'demo.light.DemoLight'."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)

SUPPORT_DEMO = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR


class FakeLight(LightEntity):
    """Representation of a fake light."""

    def __init__(
        self,
        unique_id,
        name,
        state,
        hs_color=None,
        ct=None,
        brightness=180,
    ):
        """Initialize the light."""
        self._unique_id = unique_id
        self._name = name
        self._state = state
        self._hs_color = hs_color
        self._ct = ct or 380
        self._brightness = brightness
        self._features = SUPPORT_DEMO
        self._available = True
        self._color_mode = "ct" if ct is not None and hs_color is None else "hs"

    @property
    def name(self) -> str:
        """Return the name of the light if any."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for light."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """No polling needed for a demo light."""
        return False

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._available

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self) -> tuple:
        """Return the hs color value."""
        if self._color_mode == "hs":
            return self._hs_color
        return None

    @property
    def color_temp(self) -> int:
        """Return the CT color temperature."""
        if self._color_mode == "ct":
            return self._ct
        return None

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._features

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        self._state = True

        if ATTR_HS_COLOR in kwargs:
            self._color_mode = "hs"
            self._hs_color = kwargs[ATTR_HS_COLOR]

        if ATTR_COLOR_TEMP in kwargs:
            self._color_mode = "ct"
            self._ct = kwargs[ATTR_COLOR_TEMP]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._state = False
        self.async_write_ha_state()
