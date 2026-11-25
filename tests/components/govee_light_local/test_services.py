"""Test the Govee light local services."""

from unittest.mock import AsyncMock, call

from govee_local_api import GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.light_capabilities import (
    COMMON_FEATURES,
    SCENE_CODES,
    SEGMENT_CODES,
)
import probatio
import pytest

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.light import (
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import setup_light

SEGMENT_CAPABILITIES = GoveeLightCapabilities(
    features=COMMON_FEATURES
    | GoveeLightFeatures.SEGMENT_CONTROL
    | GoveeLightFeatures.SCENES,
    segments=SEGMENT_CODES[:8],
    scenes=SCENE_CODES,
)


async def test_set_segment_color(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setting the color of segments, which ends the light's scene."""
    _, device = await setup_light(hass, mock_govee_api, SEGMENT_CAPABILITIES)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: "light.H615A", ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    assert hass.states.get("light.H615A").attributes[ATTR_EFFECT] == "sunrise"

    await hass.services.async_call(
        DOMAIN,
        "set_segment_color",
        {
            TargetKey.ENTITY_ID: "light.H615A",
            "segments": [2, 8],
            LightServiceArgument.RGB_COLOR: [255, 0, 0],
        },
        blocking=True,
    )

    assert mock_govee_api.set_segment_rgb_color.await_args_list == [
        call(device, 2, (255, 0, 0)),
        call(device, 8, (255, 0, 0)),
    ]
    assert hass.states.get("light.H615A").attributes[ATTR_EFFECT] is None


async def test_set_segment_color_without_segments(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a light without segment control refuses the call."""
    await setup_light(hass, mock_govee_api)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_segment_color",
            {
                TargetKey.ENTITY_ID: "light.H615A",
                "segments": [1],
                LightServiceArgument.RGB_COLOR: [255, 0, 0],
            },
            blocking=True,
        )

    assert err.value.translation_key == "segments_not_supported"
    mock_govee_api.set_segment_rgb_color.assert_not_called()


async def test_set_segment_color_invalid_segment(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a segment the light does not have refuses the whole call."""
    await setup_light(hass, mock_govee_api, SEGMENT_CAPABILITIES)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_segment_color",
            {
                TargetKey.ENTITY_ID: "light.H615A",
                "segments": [1, 9],
                LightServiceArgument.RGB_COLOR: [255, 0, 0],
            },
            blocking=True,
        )

    assert err.value.translation_key == "invalid_segments"
    assert err.value.translation_placeholders == {
        "entity_id": "light.h615a",
        "segments": "9",
        "count": "8",
    }
    mock_govee_api.set_segment_rgb_color.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        {"segments": [0], LightServiceArgument.RGB_COLOR: [255, 0, 0]},
        {"segments": [], LightServiceArgument.RGB_COLOR: [255, 0, 0]},
        {"segments": [1, 1], LightServiceArgument.RGB_COLOR: [255, 0, 0]},
        {"segments": [1], LightServiceArgument.RGB_COLOR: [256, 0, 0]},
        {"segments": [1]},
    ],
)
async def test_set_segment_color_schema(
    hass: HomeAssistant, mock_govee_api: AsyncMock, data: dict
) -> None:
    """Test the call is validated before anything is sent."""
    await setup_light(hass, mock_govee_api, SEGMENT_CAPABILITIES)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_segment_color",
            {TargetKey.ENTITY_ID: "light.H615A", **data},
            blocking=True,
        )

    mock_govee_api.set_segment_rgb_color.assert_not_called()
