"""Fixtures for the light entity component tests."""
from collections.abc import Callable

import pytest

from homeassistant.components.light import DOMAIN, ColorMode, LightEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockPlatform, MockToggleEntity, mock_platform

TURN_ON_ARG_TO_COLOR_MODE = {
    "hs_color": ColorMode.HS,
    "xy_color": ColorMode.XY,
    "rgb_color": ColorMode.RGB,
    "rgbw_color": ColorMode.RGBW,
    "rgbww_color": ColorMode.RGBWW,
    "color_temp_kelvin": ColorMode.COLOR_TEMP,
}


class MockLight(MockToggleEntity, LightEntity):
    """Mock light class."""

    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2000
    supported_features = 0

    brightness = None
    color_temp_kelvin = None
    hs_color = None
    rgb_color = None
    rgbw_color = None
    rgbww_color = None
    xy_color = None

    def __init__(
        self,
        name,
        state,
        unique_id=None,
        supported_color_modes: set[ColorMode] | None = None,
    ):
        """Initialize the mock light."""
        super().__init__(name, state, unique_id)
        if supported_color_modes is None:
            supported_color_modes = {ColorMode.ONOFF}
        self._attr_supported_color_modes = supported_color_modes
        color_mode = ColorMode.UNKNOWN
        if len(supported_color_modes) == 1:
            color_mode = next(iter(supported_color_modes))
        self._attr_color_mode = color_mode

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        super().turn_on(**kwargs)
        for key, value in kwargs.items():
            if key in [
                "brightness",
                "hs_color",
                "xy_color",
                "rgb_color",
                "rgbw_color",
                "rgbww_color",
                "color_temp_kelvin",
            ]:
                setattr(self, key, value)
            if key == "white":
                setattr(self, "brightness", value)
            if key in TURN_ON_ARG_TO_COLOR_MODE:
                self._attr_color_mode = TURN_ON_ARG_TO_COLOR_MODE[key]


SetupLightPlatformCallable = Callable[[list[MockLight] | None], None]


@pytest.fixture
async def mock_light_entities() -> list[MockLight]:
    """Return mocked light entities."""
    return [
        MockLight("Ceiling", STATE_ON),
        MockLight("Ceiling", STATE_OFF),
        MockLight(None, STATE_OFF),
    ]


@pytest.fixture
async def setup_light_platform(
    hass: HomeAssistant, mock_light_entities: list[MockLight]
) -> SetupLightPlatformCallable:
    """Set up the mock light entity platform."""

    def _setup(entities: list[MockLight] | None = None) -> None:
        """Set up the mock light entity platform."""

        async def async_setup_platform(
            hass: HomeAssistant,
            config: ConfigType,
            async_add_entities: AddEntitiesCallback,
            discovery_info: DiscoveryInfoType | None = None,
        ) -> None:
            """Set up test light platform."""
            async_add_entities(
                entities if entities is not None else mock_light_entities
            )

        mock_platform(
            hass,
            f"test.{DOMAIN}",
            MockPlatform(async_setup_platform=async_setup_platform),
        )

    return _setup
