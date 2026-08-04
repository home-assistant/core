"""Tests for the Theben Conexa sensors."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.theben_conexa.const import OBIS_IN, OBIS_OUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_setup_entry_logs_unsupported_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_conexa_smgw: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Supported keys are added while unsupported ones are skipped."""
    mock_conexa_smgw.client.getLatestValues = AsyncMock(
        return_value={
            OBIS_IN: SimpleNamespace(value=1, unit="Wh"),
            OBIS_OUT: SimpleNamespace(value=2, unit="Wh"),
            "1-0:3.8.0": SimpleNamespace(value=3, unit="Wh"),
        }
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    assert len(hass.states.async_entity_ids("sensor")) == 2
    assert "Skipping unsupported Conexa SMGW key" in caplog.text
