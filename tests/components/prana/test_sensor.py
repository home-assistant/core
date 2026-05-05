"""Tests for the Prana sensor platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all Prana sensors using snapshots."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.SENSOR]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_not_added_if_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_prana_api: MagicMock,
) -> None:
    """Test sensors are not added when value_fn returns None."""

    mock_prana_api.get_state.return_value.co2 = None
    mock_prana_api.get_state.return_value.humidity = 45

    with patch("homeassistant.components.prana.PLATFORMS", [Platform.SENSOR]):
        await async_init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.prana_recuperator_humidity") is not None
    assert hass.states.get("sensor.prana_recuperator_co2") is None
