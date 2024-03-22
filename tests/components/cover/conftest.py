"""Fixtures for cover entity components tests."""
from collections.abc import Callable

import pytest

from homeassistant.components.cover import DOMAIN, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import MockCover

from tests.common import MockPlatform, mock_platform

SetupCoverPlatformCallable = Callable[[list[MockCover] | None], None]


@pytest.fixture
def mock_cover_entities() -> list[MockCover]:
    """Return a list of MockCover instances."""
    return [
        MockCover(
            name="Simple cover",
            is_on=True,
            unique_id="unique_cover",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        ),
        MockCover(
            name="Set position cover",
            is_on=True,
            unique_id="unique_set_pos_cover",
            current_cover_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION,
        ),
        MockCover(
            name="Simple tilt cover",
            is_on=True,
            unique_id="unique_tilt_cover",
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT,
        ),
        MockCover(
            name="Set tilt position cover",
            is_on=True,
            unique_id="unique_set_pos_tilt_cover",
            current_cover_tilt_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
        MockCover(
            name="All functions cover",
            is_on=True,
            unique_id="unique_all_functions_cover",
            current_cover_position=50,
            current_cover_tilt_position=50,
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
        MockCover(
            name="Simple with opening/closing cover",
            is_on=True,
            unique_id="unique_opening_closing_cover",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
            reports_opening_closing=True,
        ),
    ]


@pytest.fixture
def setup_cover_platform(
    hass: HomeAssistant, mock_cover_entities: list[MockCover]
) -> SetupCoverPlatformCallable:
    """Set up the mock cover entity platform."""

    def _setup(entities: list[MockCover] | None = None) -> None:
        """Set up the mock cover entity platform."""

        async def async_setup_platform(
            hass: HomeAssistant,
            config: ConfigType,
            async_add_entities: AddEntitiesCallback,
            discovery_info: DiscoveryInfoType | None = None,
        ) -> None:
            """Set up test cover platform."""
            async_add_entities(entities if entities else mock_cover_entities)

        mock_platform(
            hass,
            f"test.{DOMAIN}",
            MockPlatform(async_setup_platform=async_setup_platform),
        )

    return _setup
