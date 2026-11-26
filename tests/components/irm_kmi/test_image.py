"""Tests for the IRM KMI image platform."""

import asyncio
from collections.abc import Generator
import copy
from datetime import datetime, timedelta
from typing import override
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
from pytest_homeassistant.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.amber import AmberDataSerializer
from syrupy.types import PropertyFilter, PropertyMatcher, PropertyPath, SerializableData

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.image import async_get_image
from homeassistant.components.irm_kmi.const import CONF_DARK_MODE, CONF_RADAR_STYLE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import ANIMATION, RADAR_ENTITY_ID, RADAR_FRAME

RADAR_SVG = load_fixture("radar.svg", "irm_kmi").encode()
OTHER_RADAR_SVG = RADAR_SVG.replace(b"#385E95", b"#393C40")


class SVGSnapshotSerializer(AmberDataSerializer):
    """Serialize SVG bytes as text."""

    @classmethod
    @override
    def _serialize(
        cls,
        data: SerializableData,
        *,
        depth: int = 0,
        exclude: PropertyFilter | None = None,
        include: PropertyFilter | None = None,
        matcher: PropertyMatcher | None = None,
        path: PropertyPath = (),
        visited: set[object] | None = None,
    ) -> str:
        if isinstance(data, bytes):
            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError:
                pass
            else:
                if decoded.lstrip().startswith("<svg"):
                    data = decoded
        return super()._serialize(
            data,
            depth=depth,
            exclude=exclude,
            include=include,
            matcher=matcher,
            path=path,
            visited=visited,
        )


class SVGImageSnapshotExtension(HomeAssistantSnapshotExtension):
    """Snapshot SVG bytes as text while keeping HA entity serialization."""

    serializer_class = SVGSnapshotSerializer


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
@pytest.mark.usefixtures("mock_get_forecasts_coord", "mock_get_image")
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
    svg_snapshot = snapshot.use_extension(SVGImageSnapshotExtension)
    assert image.content == svg_snapshot(name="radar-svg")


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

    mock_irm_kmi_api.get_animation_data.side_effect = lambda *args: {
        **copy.deepcopy(ANIMATION),
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
async def test_radar_not_cached_when_animation_changes_during_render(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    mock_rain_graph: MagicMock,
) -> None:
    """Test a render finishing after a refresh changed the radar is not cached."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await setup_integration(hass, mock_config_entry)

    rendering = asyncio.Event()
    release = asyncio.Event()

    async def slow_render() -> bytes:
        rendering.set()
        await release.wait()
        return RADAR_SVG

    mock_rain_graph.return_value.get_animated.side_effect = slow_render
    first = asyncio.create_task(async_get_image(hass, RADAR_ENTITY_ID))
    await rendering.wait()

    mock_irm_kmi_api.get_animation_data.side_effect = lambda *args: {
        **copy.deepcopy(ANIMATION),
        "hint": "Updated radar hint",
    }
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: RADAR_ENTITY_ID},
        blocking=True,
    )
    release.set()
    assert (await first).content == RADAR_SVG

    mock_rain_graph.return_value.get_animated.side_effect = None
    mock_rain_graph.return_value.get_animated.return_value = OTHER_RADAR_SVG
    assert (await async_get_image(hass, RADAR_ENTITY_ID)).content == OTHER_RADAR_SVG


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_rain_graph")
@pytest.mark.parametrize(
    ("animation_side_effect", "country"),
    [
        pytest.param(ValueError, "BE", id="animation"),
        pytest.param(None, None, id="country"),
    ],
)
async def test_radar_without_required_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    animation_side_effect: type[ValueError] | None,
    country: str | None,
) -> None:
    """Test the entity is unavailable when required radar data is missing."""
    mock_irm_kmi_api.get_animation_data.side_effect = animation_side_effect
    mock_irm_kmi_api.get_country.return_value = country

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
    mock_get_forecasts_coord: AsyncMock,
) -> None:
    """Test two views at the same time download the frames once."""
    await setup_integration(hass, mock_config_entry)

    first, second = await asyncio.gather(
        async_get_image(hass, RADAR_ENTITY_ID),
        async_get_image(hass, RADAR_ENTITY_ID),
    )

    assert first.content == second.content
    radar_frames = mock_get_forecasts_coord.return_value["animation"]["sequence"]
    assert mock_get_image.call_count == len(radar_frames) + 1


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_get_forecasts_coord")
async def test_radar_not_cached_when_frames_are_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_image: AsyncMock,
) -> None:
    """Test a radar rendered without frames is served but not cached."""

    async def location_only(url: str, params: dict[str, str] | None = None) -> bytes:
        if "getLocalizationLayer" in url:
            return RADAR_FRAME
        raise IrmKmiApiError

    mock_get_image.side_effect = location_only
    await setup_integration(hass, mock_config_entry)

    assert (await async_get_image(hass, RADAR_ENTITY_ID)).content
    calls = mock_get_image.call_count

    await async_get_image(hass, RADAR_ENTITY_ID)
    assert mock_get_image.call_count == 2 * calls


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
@pytest.mark.usefixtures("mock_get_forecasts_coord")
async def test_radar_when_the_location_layer_cannot_be_downloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_image: AsyncMock,
) -> None:
    """Test a location-layer download failure raises a translated error."""
    mock_get_image.side_effect = IrmKmiApiError

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError, match="The rain radar image could not be downloaded"
    ):
        await async_get_image(hass, RADAR_ENTITY_ID)
