"""Test the sensor provided by the Autarco integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from autarco import AutarcoConnectionError
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_sensors(
    hass: HomeAssistant,
    mock_autarco_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Autarco sensors."""
    with patch("homeassistant.components.autarco.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failed(
    hass: HomeAssistant,
    mock_autarco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable after failed update."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        hass.states.get("sensor.inverter_test_serial_1_energy_ac_output_total").state
        is not None
    )

    mock_autarco_client.get_solar.side_effect = AutarcoConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.inverter_test_serial_1_energy_ac_output_total").state
        == STATE_UNAVAILABLE
    )
