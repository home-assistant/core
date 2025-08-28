"""Tests configuration for DayBetter Local API."""

from asyncio import Event
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from daybetter_local_api import DayBetterLightCapabilities, DayBetterLightFeatures
from daybetter_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
import pytest

from homeassistant.components.daybetter_light_local.coordinator import (
    DayBetterController,
)
from homeassistant.components.daybetter_light_local.light import DayBetterLight


@pytest.fixture(name="mock_DayBetter_api")
def fixture_mock_DayBetter_api() -> Generator[AsyncMock]:
    """Set up DayBetter Local API fixture."""
    mock_api = AsyncMock(spec=DayBetterController)
    mock_api.start = AsyncMock()
    mock_api.cleanup = MagicMock(return_value=Event())
    mock_api.cleanup.return_value.set()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api.set_scene = AsyncMock()
    mock_api._async_update_data = AsyncMock()
    mock_api = AsyncMock(spec=DayBetterLight)
    # 移除这个mock，因为 coordinator.data 是从其他地方获取的
    # mock_api._async_update_data = AsyncMock(return_value=[])

    with (
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
            return_value=mock_api,
        ) as mock_controller,
        patch(
            "homeassistant.components.daybetter_light_local.config_flow.DayBetterController",
            return_value=mock_api,
        ),
    ):
        yield mock_controller.return_value


@pytest.fixture(name="mock_setup_entry")
def fixture_mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.daybetter_light_local.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


DEFAULT_CAPABILITIES: DayBetterLightCapabilities = DayBetterLightCapabilities(
    features=COMMON_FEATURES, segments=[], scenes={}
)

SCENE_CAPABILITIES: DayBetterLightCapabilities = DayBetterLightCapabilities(
    features=COMMON_FEATURES | DayBetterLightFeatures.SCENES,
    segments=[],
    scenes=SCENE_CODES,
)
