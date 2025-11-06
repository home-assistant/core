"""The binary sensor tests for the tado platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms() -> AsyncGenerator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an update of the Tado integration.

    Since the binary sensor platform doesn't infer a state immediately without extra requests,
    so adding this here to remove in a follow-up PR.
    """
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_tado_api")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of binary sensor."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
