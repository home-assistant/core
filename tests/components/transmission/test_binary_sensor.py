"""Tests for the Transmission binary sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from transmission_rpc.error import TransmissionError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the binary sensor entities."""
    with patch(
        "homeassistant.components.transmission.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_port_forwarding_unavailable_on_no_response(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test port forwarding is unknown when port_test raises an exception."""
    mock_transmission_client.return_value.port_test.side_effect = Exception(
        "Couldn't test port: No Response (0)"
    )
    with patch(
        "homeassistant.components.transmission.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.transmission_port_forwarding")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_port_forwarding_unavailable_on_transmission_error(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test port forwarding is unknown when port_test raises a TransmissionError."""
    mock_transmission_client.return_value.port_test.side_effect = TransmissionError(
        "Connection error"
    )
    with patch(
        "homeassistant.components.transmission.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.transmission_port_forwarding")
    assert state is not None
    assert state.state == "unknown"
