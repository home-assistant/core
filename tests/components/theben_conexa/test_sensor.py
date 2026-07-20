"""Tests for the Theben Conexa sensors."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.theben_conexa.const import DOMAIN, OBIS_IN, OBIS_OUT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

TEST_CONFIG_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_async_setup_entry_logs_unsupported_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_conexa_smgw: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Supported keys are added while unsupported ones are skipped."""
    mock_conexa_smgw.getLatestValues = AsyncMock(
        return_value={
            OBIS_IN: SimpleNamespace(value=1, unit="Wh"),
            OBIS_OUT: SimpleNamespace(value=2, unit="Wh"),
            "1-0:3.8.0": SimpleNamespace(value=3, unit="Wh"),
        }
    )

    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert {entry.unique_id for entry in entity_entries} == {
        f"{mock_conexa_smgw.gatewayInfo.smgwID}-{TEST_CONFIG_DATA[CONF_USERNAME]}-{OBIS_IN}",
        f"{mock_conexa_smgw.gatewayInfo.smgwID}-{TEST_CONFIG_DATA[CONF_USERNAME]}-{OBIS_OUT}",
    }
    assert len(hass.states.async_entity_ids("sensor")) == 2
    assert "Skipping unsupported Conexa SMGW key" in caplog.text
