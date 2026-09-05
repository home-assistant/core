"""Test for diagnostics platform of the LED Infrared integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.led_infrared.const import LEDIrDeviceType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    "config_entry",
    [
        LEDIrDeviceType.GENERIC_10_KEY,
        LEDIrDeviceType.GENERIC_13_KEY,
        LEDIrDeviceType.GENERIC_24_KEY,
        LEDIrDeviceType.GENERIC_40_KEY,
        LEDIrDeviceType.GENERIC_44_KEY,
    ],
    indirect=True,
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
