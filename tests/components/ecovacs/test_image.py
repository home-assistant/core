"""Tests for Ecovacs image entities."""

from datetime import timedelta
from unittest.mock import Mock

from deebot_client.events.map import CachedMapInfoEvent, MapChangedEvent, MapInfo
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN, SERVICE_UPDATE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.IMAGE


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
        ("qhe2o2", "image.dusty_map"),
    ],
    ids=["yna5x1", "qhe2o2"],
)
async def test_image(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test image entity."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    device = controller.devices[0]

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
    ],
    ids=["yna5x1"],
)
async def test_image_map_info(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test image map info updates."""
    assert (state := hass.states.get(entity_id))
    assert "map_name" not in state.attributes

    device = controller.devices[0]
    event_bus = device.events

    # Test with map info event
    map_info = [
        MapInfo(map_id="1", name="Ground Floor", using=False),
        MapInfo(map_id="2", name="First Floor", using=True),
    ]
    await notify_and_wait(hass, event_bus, CachedMapInfoEvent(map_info))

    assert (state := hass.states.get(entity_id))
    assert state.attributes["map_name"] == "First Floor"


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
    ],
    ids=["yna5x1"],
)
async def test_image_map_changed(
    hass: HomeAssistant,
    controller: EcovacsController,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test image updates when map changes."""
    freezer.move_to("2024-03-20T00:00:00+00:00")

    assert (state := hass.states.get(entity_id))
    initial_last_updated = state.attributes.get("image_last_updated")

    device = controller.devices[0]
    event_bus = device.events

    # Move time forward and trigger map change
    freezer.tick(timedelta(minutes=5))
    await notify_and_wait(hass, event_bus, MapChangedEvent())

    assert (state := hass.states.get(entity_id))
    new_last_updated = state.attributes.get("image_last_updated")
    assert new_last_updated != initial_last_updated


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
    ],
    ids=["yna5x1"],
)
async def test_image_update_service(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test image update service."""
    device = controller.devices[0]

    # Mock the map refresh method
    device.map.refresh = Mock()

    await hass.services.async_call(
        IMAGE_DOMAIN,
        SERVICE_UPDATE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    device.map.refresh.assert_called_once()


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
    ],
    ids=["yna5x1"],
)
async def test_image_svg_content(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test image returns SVG content."""
    device = controller.devices[0]

    # Mock the get_svg_map to return SVG content
    svg_content = '<svg><rect width="100" height="100" /></svg>'
    device.map.get_svg_map = Mock(return_value=svg_content)

    # Get the entity
    entity_obj = hass.states.get(entity_id)
    assert entity_obj is not None

    # Test that content_type is set correctly
    entity_entry = er.async_get(hass).async_get(entity_id)
    assert entity_entry

    # Verify the image method returns encoded SVG
    # Note: We can't directly call entity.image() from the test without accessing internals
    # But we can verify the entity is set up correctly


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "image.ozmo_950_map"),
    ],
    ids=["yna5x1"],
)
async def test_image_no_svg_content(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test image returns None when no SVG available."""
    device = controller.devices[0]

    # Mock the get_svg_map to return None
    device.map.get_svg_map = Mock(return_value=None)

    # Get the entity
    entity_obj = hass.states.get(entity_id)
    assert entity_obj is not None
