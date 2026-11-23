"""Tests for Speedtest.net diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.speedtestdotnet.const import (
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import MOCK_RESULTS, MOCK_SERVERS


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
            CONF_SERVER_ID: "1",
        },
    )
    entry.add_to_hass(hass)

    mock_api.return_value.get_best_server.return_value = MOCK_SERVERS[1][0]
    mock_api.return_value.results.dict.return_value = {
        **MOCK_RESULTS,
        "server": {**MOCK_RESULTS["server"], "sponsor": "Sponsor", "cc": "CC"},
        "client": {
            "ip": "1.2.3.4",
            "lat": "1.0",
            "lon": "2.0",
            "isp": "ISP",
            "country": "CC",
        },
    }

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
