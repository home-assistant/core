"""Test System Monitor PSI sensor."""

from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.systemmonitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_PRESSURE_INFO = {
    "cpu": {
        "some": {"avg10": 1.1, "avg60": 2.2, "avg300": 3.3, "total": 12345}    },
    "memory": {
        "some": {"avg10": 4.4, "avg60": 5.5, "avg300": 6.6, "total": 54321},
        "full": {"avg10": 0.4, "avg60": 0.5, "avg300": 0.6, "total": 432},
    },
    "io": {
        "some": {"avg10": 7.7, "avg60": 8.8, "avg300": 9.9, "total": 67890},
        "full": {"avg10": 0.7, "avg60": 0.8, "avg300": 0.9, "total": 789},
    },
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_psi_sensor(
    hass: HomeAssistant,
    mock_psutil: Mock,
    mock_os: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the PSI sensor."""
    mock_config_entry = MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={},
    )

    with patch(
        "homeassistant.components.systemmonitor.coordinator.get_all_pressure_info",
        return_value=MOCK_PRESSURE_INFO,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Use snapshot for all psi sensors
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        ):
            if "pressure" in entity.unique_id:
                state = hass.states.get(entity.entity_id)
                assert state
                assert state == snapshot(name=f"{entity.entity_id}")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_psi_sensor_unavailable(
    hass: HomeAssistant,
    mock_psutil: Mock,
    mock_os: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the PSI sensor when data is unavailable."""
    mock_config_entry = MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={},
    )

    with patch(
        "homeassistant.components.systemmonitor.coordinator.get_all_pressure_info",
        return_value={},
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Use snapshot for all psi sensors
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        ):
            if "pressure" in entity.unique_id:
                state = hass.states.get(entity.entity_id)
                assert state
                assert state == snapshot(name=f"{entity.entity_id}-unavailable")
