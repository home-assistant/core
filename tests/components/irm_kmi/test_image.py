"""Tests for the IRM KMI image platform."""

import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from irm_kmi_api import IrmKmiApiError, RadarStyle
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.image import async_get_image
from homeassistant.components.irm_kmi.const import CONF_DARK_MODE, CONF_RADAR_STYLE
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import ANIMATION, RADAR_ENTITY_ID

RADAR_SVG = load_fixture("radar.svg", "irm_kmi").encode()
OTHER_RADAR_SVG = RADAR_SVG.replace(b"#385E95", b"#393C40")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Load only the image platform."""
    with patch("homeassistant.components.irm_kmi.PLATFORMS", [Platform.IMAGE]):
        yield


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.fixture
def mock_rain_graph() -> Generator[MagicMock]:
    """Mock the radar renderer."""
    with patch(
        "homeassistant.components.irm_kmi.image.RainGraph", autospec=True
    ) as rain_graph:
        graph = rain_graph.return_value

        async def build_graph() -> MagicMock:
            for frame in rain_graph.call_args.kwargs["animation_data"]["sequence"]:
                frame["image"] = b"frame"
            return graph

        graph.build.side_effect = build_graph
        graph.get_animated.return_value = RADAR_SVG
        yield rain_graph


async def next_refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator poll the API once more."""
    freezer.tick(timedelta(minutes=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_irm_kmi_api", "mock_rain_graph")
async def test_radar_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the radar image entity and the bytes it serves."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content_type == "image/svg+xml"
    assert image.content == RADAR_SVG


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_radar_refresh_with_changed_animation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    mock_rain_graph: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a changed radar loop is rendered again after a polling refresh."""
    mock_rain_graph.return_value.get_animated.side_effect = [
        RADAR_SVG,
        OTHER_RADAR_SVG,
    ]

    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == RADAR_SVG

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state is not None
    initial_timestamp = datetime.fromisoformat(state.state)

    mock_irm_kmi_api.get_animation_data.return_value = {
        **ANIMATION,
        "hint": "Updated radar hint",
    }
    await next_refresh(hass, freezer)

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == OTHER_RADAR_SVG
    assert mock_rain_graph.call_count == 2

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state is not None
    assert datetime.fromisoformat(state.state) > initial_timestamp


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_radar_refresh_with_unchanged_animation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    mock_rain_graph: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unchanged radar loop keeps the rendered image and timestamp."""
    mock_rain_graph.return_value.get_animated.side_effect = [
        RADAR_SVG,
        OTHER_RADAR_SVG,
    ]

    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == RADAR_SVG

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state is not None
    initial_timestamp = datetime.fromisoformat(state.state)

    await next_refresh(hass, freezer)

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == RADAR_SVG
    mock_rain_graph.assert_called_once()

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state is not None
    assert datetime.fromisoformat(state.state) == initial_timestamp


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_rain_graph")
async def test_radar_without_animation_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
) -> None:
    """Test the entity is unavailable when the payload carries no radar loop."""
    mock_irm_kmi_api.get_animation_data.side_effect = ValueError

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, RADAR_ENTITY_ID)


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_rain_graph")
async def test_radar_without_country(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
) -> None:
    """Test the entity is unavailable when the country is missing."""
    mock_irm_kmi_api.get_country.return_value = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(RADAR_ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, RADAR_ENTITY_ID)


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_radar_style_option_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    mock_rain_graph: MagicMock,
) -> None:
    """Test the radar options reach both the frame URLs and the rendering."""
    await setup_integration(hass, mock_config_entry)

    assert mock_irm_kmi_api.get_animation_data.call_args.args[2:] == (
        RadarStyle.OPTION_STYLE_STD,
        False,
    )
    mock_rain_graph.assert_not_called()

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == RADAR_SVG
    assert mock_rain_graph.call_args.kwargs["style"] == RadarStyle.OPTION_STYLE_STD
    assert mock_rain_graph.call_args.kwargs["dark_mode"] is False

    mock_rain_graph.return_value.get_animated.return_value = OTHER_RADAR_SVG

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RADAR_STYLE: RadarStyle.OPTION_STYLE_SATELLITE,
            CONF_DARK_MODE: True,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert mock_irm_kmi_api.get_animation_data.call_args.args[2:] == (
        RadarStyle.OPTION_STYLE_SATELLITE,
        True,
    )

    image = await async_get_image(hass, RADAR_ENTITY_ID)
    assert image.content == OTHER_RADAR_SVG
    assert (
        mock_rain_graph.call_args.kwargs["style"] == RadarStyle.OPTION_STYLE_SATELLITE
    )
    assert mock_rain_graph.call_args.kwargs["dark_mode"] is True


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_get_forecasts_coord")
async def test_radar_concurrent_views_share_one_download(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_image: AsyncMock,
) -> None:
    """Test two views at the same time download the frames once."""
    await setup_integration(hass, mock_config_entry)

    first, second = await asyncio.gather(
        async_get_image(hass, RADAR_ENTITY_ID),
        async_get_image(hass, RADAR_ENTITY_ID),
    )

    assert first.content == second.content
    assert mock_get_image.call_count == 12


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_get_forecasts_coord")
async def test_radar_when_the_frames_cannot_be_downloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_image: AsyncMock,
) -> None:
    """Test a frame download failure raises a translated error."""
    mock_get_image.side_effect = IrmKmiApiError

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError, match="The rain radar image could not be downloaded"
    ):
        await async_get_image(hass, RADAR_ENTITY_ID)
