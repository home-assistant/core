"""Tests for the NeoPool coordinator."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.neopool.const import (
    CONF_CAPABILITIES,
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CURRENT_VERSION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_NAME, MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_neopool_client")
async def test_winter_mode_skips_modbus(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
) -> None:
    """When winter mode is on we never call async_read_all, even on manual refresh."""
    snapshot = {"MBF_PAR_FILT_GPIO": 1, "MBF_PAR_LIGHTING_GPIO": 2}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Winter Pool",
        unique_id="neopool_winter",
        version=CURRENT_VERSION,
        pref_disable_polling=True,
        data={
            "host": "192.0.2.5",
            "port": 502,
            "name": "Winter Pool",
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={
            CONF_MODBUS_FRAMER: "tcp",
            CONF_CAPABILITIES: snapshot,
        },
    )
    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert mock_neopool_client.async_read_all.await_count == 0

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert mock_neopool_client.async_read_all.await_count == 0


@pytest.mark.usefixtures("mock_neopool_client")
async def test_persisted_snapshot_recreates_entity_set(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The persisted capability snapshot recreates the live entity set offline.

    A live poll registers a capability-gated set of entities and persists the
    capability snapshot. A second entry loaded in winter mode from only that
    snapshot, with no Modbus read, must register the same set. This proves the
    snapshot carries every key the platform supported_fn callbacks consult, so
    a key dropped from CAPABILITY_KEYS would be caught here.
    """
    await setup_integration(hass, mock_config_entry)
    live = {
        e.unique_id.removeprefix(f"{mock_config_entry.unique_id}_")
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert live

    snapshot = mock_config_entry.options[CONF_CAPABILITIES]
    offline_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"{MOCK_SERIAL}_offline",
        version=CURRENT_VERSION,
        pref_disable_polling=True,
        data={
            "host": MOCK_HOST,
            "port": MOCK_PORT,
            "name": MOCK_NAME,
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={
            CONF_MODBUS_FRAMER: "tcp",
            CONF_CAPABILITIES: snapshot,
        },
    )
    await setup_integration(hass, offline_entry)
    assert offline_entry.state is ConfigEntryState.LOADED

    offline = {
        e.unique_id.removeprefix(f"{offline_entry.unique_id}_")
        for e in er.async_entries_for_config_entry(
            entity_registry, offline_entry.entry_id
        )
    }
    assert offline == live
