"""Tests for the NZBGet integration."""
from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_HOST: "10.10.10.30",
    CONF_NAME: "GetNZBsTest",
    CONF_PASSWORD: None,
    CONF_PORT: 6789,
    CONF_SCAN_INTERVAL: 5,
    CONF_SSL: False,
    CONF_USERNAME: None,
}

MOCK_VERSION = "21.0"

MOCK_STATUS = {
    "ArticleCacheMB": "",
    "AverageDownloadRate": "",
    "DownloadPaused": "",
    "DownloadRate": "",
    "DownloadedSizeMB": "",
    "FreeDiskSpaceMB": "",
    "PostJobCount": "",
    "PostPaused": "",
    "RemainingSizeMB": "",
    "UpTimeSec": "",
}

MOCK_HISTORY = [
    {"Name": "Downloaded Item XYZ", "Category": "", "Status": "SUCCESS"},
    {"Name": "Failed Item ABC", "Category": "", "Status": "FAILURE"},
]


async def init_integration(
    hass,
    *,
    status: dict = MOCK_STATUS,
    history: dict = MOCK_HISTORY,
    version: str = MOCK_VERSION,
) -> MockConfigEntry:
    """Set up the NZBGet integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)

    with patch(
        "homeassistant.components.nzbget.NZBGetAPI.version", return_value=version,
    ), patch(
        "homeassistant.components.nzbget.NZBGetAPI.status", return_value=status,
    ), patch(
        "homeassistant.components.nzbget.NZBGetAPI.history", return_value=history,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
