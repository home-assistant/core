"""Binary sensor tests for Intergas InComfort integration."""

from unittest.mock import MagicMock, patch

from incomfortclient import FaultCode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_HEATER_STATUS

from tests.common import snapshot_platform


@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_setup_platform(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort entities are set up correctly."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_heater_status",
    [
        MOCK_HEATER_STATUS
        | {
            "is_failed": True,
            "display_code": None,
            "fault_code": FaultCode.CV_TEMPERATURE_TOO_HIGH_E1,
        },
        MOCK_HEATER_STATUS | {"is_pumping": True},
        MOCK_HEATER_STATUS | {"is_burning": True},
        MOCK_HEATER_STATUS | {"is_tapping": True},
    ],
    ids=["is_failed", "is_pumping", "is_burning", "is_tapping"],
)
@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_setup_binary_sensors_alt(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort heater ."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
