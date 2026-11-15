"""Tests for the Bambu Lab sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiobambulab import PrintState
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

PRINT_STATUS = "sensor.x1_carbon_print_status"


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors of a printer."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_chamber_temperature(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a printer without chamber sensor has no sensor for it."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, chamber_temperature=None
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.x1_carbon_nozzle_temperature") is not None
    assert hass.states.get("sensor.x1_carbon_chamber_temperature") is None


async def test_update(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors follow what the printer pushes."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state,
        print_state=PrintState.PAUSED,
        progress=43,
        remaining_minutes=None,
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == "paused"
    assert hass.states.get("sensor.x1_carbon_print_progress").state == "43"
    assert hass.states.get("sensor.x1_carbon_remaining_time").state == STATE_UNKNOWN


async def test_unavailable(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors are unavailable while the printer is not connected."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.available = False
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == STATE_UNAVAILABLE

    mock_bambu_lab_client.available = True
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == "printing"
