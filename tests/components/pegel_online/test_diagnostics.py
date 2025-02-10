"""Test pegel_online diagnostics."""

from unittest.mock import patch

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.pegel_online.const import CONF_STATION, DOMAIN
from homeassistant.core import HomeAssistant

from . import PegelOnlineMock
from .const import (
    MOCK_CONFIG_ENTRY_DATA_DRESDEN,
    MOCK_STATION_DETAILS_DRESDEN,
    MOCK_STATION_MEASUREMENT_DRESDEN,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA_DRESDEN,
        unique_id=MOCK_CONFIG_ENTRY_DATA_DRESDEN[CONF_STATION],
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.pegel_online.PegelOnline") as pegelonline:
        pegelonline.return_value = PegelOnlineMock(
            station_details=MOCK_STATION_DETAILS_DRESDEN,
            station_measurements=MOCK_STATION_MEASUREMENT_DRESDEN,
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
