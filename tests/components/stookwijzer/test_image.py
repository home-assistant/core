"""Tests for the Stookwijzer image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from stookwijzer import MapOptions
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "image.stookwijzer_map"


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock the image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the image platform."""
    return [Platform.IMAGE]


@pytest.mark.freeze_time("2025-02-12 16:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Stookwijzer image entity."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_image_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the image entity is disabled by default."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test the image returns the map with translated legend labels."""
    state = hass.states.get(ENTITY_ID)
    assert state

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    assert await resp.read() == b"stookwijzer_map_png"
    mock_stookwijzer.return_value.async_get_map.assert_called_once_with(
        MapOptions(
            labels={
                "code_yellow": "Code yellow",
                "code_orange": "Code orange",
                "code_red": "Code red",
            }
        )
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_no_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test there is no image when the map could not be rendered."""
    mock_stookwijzer.return_value.async_get_map.return_value = None
    state = hass.states.get(ENTITY_ID)
    assert state

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.freeze_time("2025-02-12 16:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_image_updated_on_coordinator_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the image is marked as changed after a coordinator update."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "2025-02-12T16:00:00+00:00"

    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "2025-02-12T17:00:00+00:00"
