"""Tests for OneDrive sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from onedrive_personal_sdk.exceptions import HttpRequestException
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the OneDrive sensors."""

    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure sensors are going unavailable on update failure."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.remaining_onedrive_size")
    assert state.state == "0.75"

    mock_onedrive_client.get_drive.side_effect = HttpRequestException(
        503, "Service Unavailable"
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.remaining_onedrive_size")
    assert state.state == STATE_UNAVAILABLE
