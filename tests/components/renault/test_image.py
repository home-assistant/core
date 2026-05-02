"""Tests for Renault image entities."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.IMAGE]):
        yield


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_50"], indirect=True)
async def test_images_no_picture(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no image entities are created when vehicle has no picture."""
    with patch(
        "renault_api.kamereon.models.KamereonVehicleDetails.get_picture",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0


@pytest.mark.freeze_time("2024-01-01 00:00:00+00:00")
@pytest.mark.usefixtures("fixtures_with_data")
async def test_images(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault image entities."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
