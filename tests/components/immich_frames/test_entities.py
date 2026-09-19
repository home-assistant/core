"""Test Immich Frames entity behavior."""

from copy import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aioimmich.assets.models import ExifInfo

from homeassistant.components.immich_frames.button import FrameButton
from homeassistant.components.immich_frames.const import (
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
)
from homeassistant.components.immich_frames.coordinator import (
    ImmichFramesConfigEntry,
    ImmichFramesData,
    ImmichFramesDataUpdateCoordinator,
)
from homeassistant.components.immich_frames.image import ImmichFrameImage
from homeassistant.components.immich_frames.sensor import (
    PhotoSensor,
    _photo_date,
    _photo_location,
    _photo_people,
)
from homeassistant.components.immich_frames.switch import SlideshowSwitch
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.immich.const import MOCK_SEARCH_ASSETS


def _coordinator(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> ImmichFramesDataUpdateCoordinator:
    """Create a coordinator with deterministic entity data."""
    entry: ImmichFramesConfigEntry = MockConfigEntry(
        domain="immich_frames",
        title="Entity test",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Entity test",
        },
    )
    entry.add_to_hass(hass)
    coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
    asset = copy(MOCK_SEARCH_ASSETS[0])
    asset.exif_info = ExifInfo(city="London", country="UK")
    asset.people = [SimpleNamespace(name="Alex"), "Camera"]
    coordinator.data = ImmichFramesData(
        asset=asset,
        image=b"image",
        updated_at=datetime.now(UTC),
        matching_assets=3,
    )
    return coordinator


async def test_metadata_entities_and_controls(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Metadata values, image bytes, buttons, and slideshow state are usable."""
    coordinator = _coordinator(hass, parent_immich_entry)

    assert _photo_date(coordinator.data).endswith("2023")
    assert _photo_location(coordinator.data) == "London, UK"
    assert _photo_people(coordinator.data) == "Alex, Camera"

    sensor = PhotoSensor(coordinator, "photo_people", _photo_people)
    assert sensor.native_value == "Alex, Camera"
    coordinator.data = None
    assert PhotoSensor(coordinator, "status", lambda data: data).native_value is None
    coordinator.data = ImmichFramesData(
        asset=MOCK_SEARCH_ASSETS[0], image=b"image", updated_at=datetime.now(UTC)
    )

    image = ImmichFrameImage(coordinator)
    assert await image.async_image() == b"image"

    action = AsyncMock()
    button = FrameButton(coordinator, "next", action)
    await button.async_press()
    action.assert_awaited_once()

    switch = SlideshowSwitch(coordinator)
    with patch.object(switch, "async_write_ha_state") as write_state:
        await switch.async_turn_off()
        assert switch.is_on is False
        await switch.async_turn_on()
        assert switch.is_on is True
        assert write_state.call_count == 2
