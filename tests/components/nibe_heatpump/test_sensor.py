"""Test the Nibe Heat Pump sensor entities."""

from typing import Any
from unittest.mock import patch

from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_add_model

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Model.F1155, {43005: 1234, 40004: 20.0, 40321: 50, 40317: 0, 43431: "OFF"}),
        (Model.SMOS40, {40019: 1234, 30002: 20.0, 31855: 50}),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: Model,
    data: dict[int, Any],
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test standard sensor entities."""
    coils.update(data)
    entry = await async_add_model(hass, model)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Model.F1155, {49239: "OFF", 47209: -100}),
        (Model.SMOS40, {31067: "Off"}),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_ignored_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: Model,
    data: dict[int, Any],
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test writeable entities are ignored."""
    coils.update(data)
    entry = await async_add_model(hass, model)
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert entity_entries == []
