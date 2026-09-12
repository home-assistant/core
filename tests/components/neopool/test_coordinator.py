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

from . import setup_integration

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
