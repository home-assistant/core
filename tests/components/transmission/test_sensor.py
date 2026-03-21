"""Tests for the Transmission sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_stats_sensors(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test session and cumulative stats sensors."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Session download: 10 GiB = 10.0 GB
    state = hass.states.get("sensor.transmission_session_download")
    assert state is not None
    assert float(state.state) == pytest.approx(10.0, rel=1e-3)

    # Session upload: 5 GiB = 5.0 GB
    state = hass.states.get("sensor.transmission_session_upload")
    assert state is not None
    assert float(state.state) == pytest.approx(5.0, rel=1e-3)

    # Total download: 100 GiB = 100.0 GB
    state = hass.states.get("sensor.transmission_total_download")
    assert state is not None
    assert float(state.state) == pytest.approx(100.0, rel=1e-3)

    # Total upload: 80 GiB = 80.0 GB
    state = hass.states.get("sensor.transmission_total_upload")
    assert state is not None
    assert float(state.state) == pytest.approx(80.0, rel=1e-3)

    # Session ratio: 5/10 = 0.5
    state = hass.states.get("sensor.transmission_session_ratio")
    assert state is not None
    assert float(state.state) == pytest.approx(0.5, rel=1e-3)

    # Total ratio: 80/100 = 0.8
    state = hass.states.get("sensor.transmission_total_ratio")
    assert state is not None
    assert float(state.state) == pytest.approx(0.8, rel=1e-3)
