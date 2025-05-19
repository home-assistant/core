"""Tests for the diagnostics data provided by the Jewish Calendar integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.jewish_calendar.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("location_data"),
    ["Jerusalem", "New York", None],
    indirect=True,
)
async def test_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics with different locations."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    # Verify that location data is redacted in entry_data
    for key in TO_REDACT:
        if key in diagnostics_data["entry_data"]:
            assert diagnostics_data["entry_data"][key] == "**REDACTED**"

    # Verify the runtime_data is included and location properties are redacted
    assert "data" in diagnostics_data
    if "location" in diagnostics_data["data"]:
        for key in TO_REDACT:
            assert key in diagnostics_data["data"]["location"]
            assert diagnostics_data["data"]["location"][key] == "**REDACTED**"

    # Complete snapshot test
    assert diagnostics_data == snapshot
