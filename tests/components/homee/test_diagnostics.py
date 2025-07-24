"""Test homee diagnostics."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homee.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import build_mock_node, setup_integration
from .conftest import HOMEE_ID

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def setup_mock_homee(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the number platform."""
    mock_homee.nodes = [
        build_mock_node("numbers.json"),
        build_mock_node("thermostat_with_currenttemp.json"),
        build_mock_node("cover_with_position_slats.json"),
    ]
    mock_homee.get_node_by_id = lambda node_id: mock_homee.nodes[node_id - 1]
    await setup_integration(hass, mock_config_entry)


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    await setup_mock_homee(hass, mock_homee, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == snapshot


async def test_diagnostics_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a device."""
    await setup_mock_homee(hass, mock_homee, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{HOMEE_ID}-1")}
    )
    assert device_entry is not None
    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )
    assert result == snapshot


async def test_diagnostics_homee_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for the homee hub device."""
    mock_homee.nodes = [
        build_mock_node("homee.json"),
    ]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{HOMEE_ID}")}
    )
    assert device_entry is not None
    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )
    assert result == snapshot
