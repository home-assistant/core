"""Test the sensors provided by the Powerfox integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from powerfox import DeviceReport, PowerfoxConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.powerfox.coordinator import (
    PowerfoxReportDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Powerfox sensors."""
    with patch("homeassistant.components.powerfox.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failed(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable after failed update."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.poweropti_energy_usage").state is not None

    mock_powerfox_client.device.side_effect = PowerfoxConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.poweropti_energy_usage").state == STATE_UNAVAILABLE


async def test_skips_gas_sensors_when_report_missing(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test gas sensors are not created when report lacks gas data."""
    mock_powerfox_client.report.return_value = DeviceReport(gas=None)

    with patch("homeassistant.components.powerfox.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.gasopti_gas_consumption_today") is None


async def test_gas_sensor_handles_missing_report(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test gas sensor returns None when report data disappears."""
    with patch("homeassistant.components.powerfox.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    gas_sensor = hass.states.get("sensor.gasopti_gas_consumption_today")
    assert gas_sensor is not None

    report_coordinator = next(
        coordinator
        for coordinator in mock_config_entry.runtime_data
        if isinstance(coordinator, PowerfoxReportDataUpdateCoordinator)
    )

    mock_powerfox_client.report.return_value = DeviceReport(gas=None)
    await report_coordinator.async_request_refresh()

    assert (
        hass.states.get("sensor.gasopti_gas_consumption_today").state == STATE_UNKNOWN
    )
