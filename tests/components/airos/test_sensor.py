"""Test the Ubiquiti airOS sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airos.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("exception"),
    [
        AirOSConnectionAuthenticationError,
        TimeoutError,
        AirOSDeviceConnectionError,
        AirOSDataMissingError,
    ],
)
async def test_sensor_update_exception_handling(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity update data handles exceptions."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    expected_entity_id = "sensor.nanostation_5ac_ap_name_antenna_gain"
    signal_state = hass.states.get(expected_entity_id)

    assert signal_state.state == "13", f"Expected state 13, got {signal_state.state}"
    assert signal_state.attributes.get("unit_of_measurement") == "dB", (
        f"Expected unit 'dB', got {signal_state.attributes.get('unit_of_measurement')}"
    )

    mock_airos_client.login.side_effect = exception

    freezer.tick(timedelta(seconds=SCAN_INTERVAL.total_seconds()))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    signal_state = hass.states.get(expected_entity_id)

    assert signal_state.state == STATE_UNAVAILABLE, (
        f"Expected state {STATE_UNAVAILABLE}, got {signal_state.state}"
    )

    mock_airos_client.login.side_effect = None

    freezer.tick(timedelta(seconds=SCAN_INTERVAL.total_seconds()))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    signal_state = hass.states.get(expected_entity_id)
    assert signal_state.state == "13", f"Expected state 13, got {signal_state.state}"
