"""Tests for Hypontech binary sensors."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Hypontech binary sensors."""
    with patch(
        "homeassistant.components.hypontech._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_unknown_status(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Hypontech binary sensor with an unexpected plant status."""
    mock_hyponcloud.get_list.return_value[0] = replace(
        mock_hyponcloud.get_list.return_value[0],
        status="maintenance",
    )

    with patch(
        "homeassistant.components.hypontech._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.balcon_connectivity")
    assert state is not None
    assert state.state == STATE_UNKNOWN
