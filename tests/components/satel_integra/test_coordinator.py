"""Test Satel Integra coordinators."""

from unittest.mock import MagicMock

from satel_integra.satel_integra import AlarmState

from homeassistant.components.satel_integra.const import ZONES
from homeassistant.components.satel_integra.coordinator import (
    SatelIntegraOutputsCoordinator,
    SatelIntegraPartitionsCoordinator,
    SatelIntegraZonesCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_zones_coordinator_callback(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zones coordinator callback setup and results."""
    coordinator = SatelIntegraZonesCoordinator(
        hass=hass,
        entry=mock_config_entry,
        client=mock_client,
    )

    # Ensure callback was registered
    assert mock_client.zones_update_callback is not None

    # Simulate incoming data from the alarm
    status = {
        ZONES: {
            1: 1,
            2: 0,
            3: 1,
        }
    }

    mock_client.zones_update_callback(status)

    await hass.async_block_till_done()

    assert coordinator.data == {
        1: True,
        2: False,
        3: True,
    }


async def test_outputs_coordinator_callback(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test outputs coordinator callback setup and results."""
    coordinator = SatelIntegraOutputsCoordinator(
        hass=hass,
        entry=mock_config_entry,
        client=mock_client,
    )

    assert mock_client.outputs_update_callback is not None

    status = {
        "outputs": {
            10: 1,
            11: 0,
        }
    }

    mock_client.outputs_update_callback(status)

    await hass.async_block_till_done()

    assert coordinator.data == {
        10: True,
        11: False,
    }


async def test_partitions_coordinator_callback(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test partitions coordinator callback setup and results."""
    coordinator = SatelIntegraPartitionsCoordinator(
        hass=hass,
        entry=mock_config_entry,
        client=mock_client,
    )

    assert mock_client.partitions_update_callback is not None

    mock_client.controller.partition_states = {
        AlarmState.ARMED_MODE0: [1, 2],
        AlarmState.TRIGGERED: [3],
    }

    mock_client.partitions_update_callback()

    await hass.async_block_till_done()

    assert coordinator.data == {
        AlarmState.ARMED_MODE0: [1, 2],
        AlarmState.TRIGGERED: [3],
    }
