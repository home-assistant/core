"""Test the Nibe Heat Pump binary sensor entities."""

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
    with patch(
        "homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.parametrize(
    ("model", "address", "value"),
    [
        (Model.F1255, 49239, "OFF"),
        (Model.F1255, 49239, "ON"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: Model,
    address: int,
    value: Any,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    coils[address] = value

    entry = await async_add_model(hass, model)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
