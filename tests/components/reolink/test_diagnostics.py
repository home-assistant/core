"""Test Reolink diagnostics."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from reolink_aio.api import Chime
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "reolink_host")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    reolink_host: MagicMock,
    reolink_chime: Chime,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Reolink diagnostics."""
    reolink_host.wifi_connection.return_value = True

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot
