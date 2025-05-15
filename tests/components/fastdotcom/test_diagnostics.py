"""Test the Fast.com component diagnostics."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test if get_config_entry_diagnostics returns the correct data."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        source=SOURCE_USER,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        return_value={
            "download_speed": 100.0,
            "upload_speed": 50.0,
            "unloaded_ping": 15.2,
            "loaded_ping": 20.5,
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot
