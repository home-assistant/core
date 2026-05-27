"""Tests for the energieleser sensor platform."""

from unittest.mock import AsyncMock

from energieleser import GasleserDevice, WaermeleserDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the energieleser integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_energieleser_client"
)
async def test_stromleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test all stromleser sensors against a snapshot."""
    await _setup_integration(hass, mock_stromleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_stromleser_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gasleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_device: GasleserDevice,
    mock_gasleser_config_entry: MockConfigEntry,
) -> None:
    """Test all gasleser sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_gasleser_device
    await _setup_integration(hass, mock_gasleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_gasleser_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_waermeleser_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_energieleser_client: AsyncMock,
    mock_waermeleser_device: WaermeleserDevice,
    mock_waermeleser_config_entry: MockConfigEntry,
) -> None:
    """Test all wärmeleser sensors against a snapshot."""
    mock_energieleser_client.get_device.return_value = mock_waermeleser_device
    await _setup_integration(hass, mock_waermeleser_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_waermeleser_config_entry.entry_id
    )
