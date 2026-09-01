"""Tests for the Theben Conexa sensors."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.theben_conexa.const import DOMAIN, OBIS_IN, OBIS_OUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_setup_entry_logs_unsupported_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check that supported keys are added while unsupported ones are skipped."""
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_conexa_smgw.client.gatewayInfo.smgwID),
        mock_config_entry.entry_id,
    )
    assert device is not None
    assert device.sw_version == mock_conexa_smgw.client.gatewayInfo.firmwareVersion
    assert len(hass.states.async_entity_ids("sensor")) == 2
    assert "Skipping unsupported Conexa SMGW key" in caplog.text
