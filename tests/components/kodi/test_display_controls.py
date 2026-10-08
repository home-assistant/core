"""Tests for Kodi picture and subtitle controls."""

import math
from unittest.mock import AsyncMock, MagicMock

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
import pytest

from homeassistant.components.kodi import button as kodi_button
from homeassistant.components.kodi.coordinator import KodiPlaybackCoordinator
from homeassistant.components.kodi.number import NUMBERS, KodiPlaybackNumber
from homeassistant.components.number import NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(hass: HomeAssistant) -> KodiPlaybackCoordinator:
    """Create a coordinator with video and supported display controls."""
    kodi = MagicMock()
    kodi.get_players = AsyncMock(return_value=[{"playerid": 1, "type": "video"}])
    kodi.get_player_properties = AsyncMock(return_value={"subtitleenabled": True})

    async def call_method(method: str, **kwargs: object) -> object:
        if method == "Player.GetViewMode":
            return {
                "verticalshift": 0.2,
                "zoom": 1.1,
                "pixelratio": 1.0,
                "nonlinearstretch": False,
                "viewmode": "custom",
            }
        if method == "Settings.GetSettingValue":
            return {
                "value": {
                    "subtitles.align": 2,
                    "subtitles.marginvertical": 6.0,
                    "subtitles.opacity": 80,
                }[kwargs["setting"]]
            }
        if method == "Settings.GetSettings":
            return {"settings": [{"id": "subtitles.marginvertical", "default": 4.95}]}
        if method == "XBMC.GetInfoLabels":
            return {
                "Player.Process(VideoFPS)": "23.976",
                "VideoPlayer.HdrType": "dolbyvision",
            }
        if method == "Settings.SetSettingValue":
            return True
        return "OK"

    kodi.call_method = AsyncMock(side_effect=call_method)
    entry = MockConfigEntry(domain="kodi", data={"name": "Kodi"})
    return KodiPlaybackCoordinator(hass, entry, MagicMock(connected=True), kodi)


async def test_slider_ranges_and_values(coordinator: KodiPlaybackCoordinator) -> None:
    """Expose picture shift and subtitle margin as Kodi-accurate sliders."""
    await coordinator.async_refresh()
    assert NUMBERS[0].mode is NumberMode.SLIDER
    picture = KodiPlaybackNumber(coordinator, NUMBERS[0])
    margin = KodiPlaybackNumber(coordinator, NUMBERS[1])
    assert picture.mode is NumberMode.SLIDER
    assert (picture.native_min_value, picture.native_max_value) == (-2.0, 2.0)
    assert picture.native_value == 0.2
    assert margin.native_min_value == 0
    assert margin.native_max_value == 50
    assert margin.native_step == 0.05
    assert margin.native_value == 6.0
    assert margin.available


async def test_picture_shift_uses_two_decimal_precision(
    coordinator: KodiPlaybackCoordinator,
) -> None:
    """Keep the picture slider's step and reported value to two decimals."""
    await coordinator.async_refresh()
    coordinator.data["picture_vertical_shift"] = 0.256
    picture = KodiPlaybackNumber(coordinator, NUMBERS[0])
    assert picture.native_step == 0.01
    assert picture.native_value == 0.26


@pytest.mark.parametrize("value", [-2.0, -1.0, -0.01, 0.0, 0.01, 1.0, 2.0])
async def test_picture_shift_bidirectional_write(
    coordinator: KodiPlaybackCoordinator, value: float
) -> None:
    """Set either direction and preserve all unrelated Kodi view-mode values."""
    await coordinator.async_refresh()
    entity = KodiPlaybackNumber(coordinator, NUMBERS[0])
    await entity.async_set_native_value(value)
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetViewMode",
        viewmode={
            "verticalshift": value,
            "zoom": 1.1,
            "pixelratio": 1.0,
            "nonlinearstretch": False,
        },
    )


@pytest.mark.parametrize("value", [0.0, 0.5, 17.35, 50.0])
async def test_subtitle_margin_write(
    coordinator: KodiPlaybackCoordinator, value: float
) -> None:
    """Write the absolute Kodi subtitle margin without changing alignment."""
    await coordinator.async_refresh()
    entity = KodiPlaybackNumber(coordinator, NUMBERS[1])
    await entity.async_set_native_value(value)
    coordinator.kodi.call_method.assert_any_await(
        "Settings.SetSettingValue", setting="subtitles.marginvertical", value=value
    )
    assert all(
        call.kwargs.get("setting") != "subtitles.align"
        for call in coordinator.kodi.call_method.await_args_list
        if call.args[0] == "Settings.SetSettingValue"
    )


async def test_reset_picture_to_center(coordinator: KodiPlaybackCoordinator) -> None:
    """Reset picture shift to zero while preserving the other view settings."""
    await coordinator.async_refresh()
    assert hasattr(kodi_button, "KodiDisplayResetButton")
    button = kodi_button.KodiDisplayResetButton(coordinator, kodi_button.BUTTONS[0])
    await button.async_press()
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetViewMode",
        viewmode={
            "verticalshift": 0.0,
            "zoom": 1.1,
            "pixelratio": 1.0,
            "nonlinearstretch": False,
        },
    )


async def test_reset_subtitle_margin_to_kodi_default(
    coordinator: KodiPlaybackCoordinator,
) -> None:
    """Restore the default read from Kodi instead of hard-coding it."""
    await coordinator.async_refresh()
    assert hasattr(kodi_button, "KodiDisplayResetButton")
    button = kodi_button.KodiDisplayResetButton(coordinator, kodi_button.BUTTONS[1])
    await button.async_press()
    coordinator.kodi.call_method.assert_any_await(
        "Settings.GetSettings", level="expert"
    )
    coordinator.kodi.call_method.assert_any_await(
        "Settings.SetSettingValue", setting="subtitles.marginvertical", value=4.95
    )


@pytest.mark.parametrize("value", [-2.01, 2.01, math.nan, math.inf])
async def test_invalid_picture_shift(
    coordinator: KodiPlaybackCoordinator, value: float
) -> None:
    """Reject values outside the supported vertical shift range."""
    await coordinator.async_refresh()
    with pytest.raises(ServiceValidationError):
        await KodiPlaybackNumber(coordinator, NUMBERS[0]).async_set_native_value(value)


@pytest.mark.parametrize("value", [-0.05, 50.05, 1.01, math.nan, math.inf])
async def test_invalid_subtitle_margin(
    coordinator: KodiPlaybackCoordinator, value: float
) -> None:
    """Reject out-of-range margin and values Kodi cannot represent by 0.05 steps."""
    await coordinator.async_refresh()
    with pytest.raises(ServiceValidationError):
        await KodiPlaybackNumber(coordinator, NUMBERS[1]).async_set_native_value(value)


async def test_optional_protocol_errors(coordinator: KodiPlaybackCoordinator) -> None:
    """Unsupported optional calls do not make stream information unavailable."""
    coordinator.kodi.call_method.side_effect = ProtocolError(
        -32601, "unsupported", None
    )
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["player"]["type"] == "video"
    assert not KodiPlaybackNumber(coordinator, NUMBERS[0]).available
    assert not KodiPlaybackNumber(coordinator, NUMBERS[1]).available


@pytest.mark.parametrize(
    "error", [ProtocolError(-32100, "failed", None), TransportError("offline")]
)
async def test_reset_failure_is_reported(
    coordinator: KodiPlaybackCoordinator, error: Exception
) -> None:
    """Surface Kodi errors from a reset command."""
    await coordinator.async_refresh()
    original = coordinator.kodi.call_method.side_effect

    async def fail_write(method: str, **kwargs: object) -> object:
        if method == "Settings.SetSettingValue":
            raise error
        return await original(method, **kwargs)

    coordinator.kodi.call_method.side_effect = fail_write
    assert hasattr(kodi_button, "KodiDisplayResetButton")
    with pytest.raises(HomeAssistantError):
        await kodi_button.KodiDisplayResetButton(
            coordinator, kodi_button.BUTTONS[1]
        ).async_press()
