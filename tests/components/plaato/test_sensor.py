"""Tests for the plaato sensors."""

from unittest.mock import patch

from pyplaato.models.device import PlaatoDeviceType
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


@pytest.mark.parametrize(
    "device_type", [PlaatoDeviceType.Airlock, PlaatoDeviceType.Keg]
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device_type: PlaatoDeviceType,
) -> None:
    """Test sensors."""
    with patch(
        "homeassistant.components.plaato.PLATFORMS",
        [Platform.SENSOR],
    ):
        entry = await init_integration(hass, device_type)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
