"""Tests for the NZBGet integration."""

from unittest.mock import patch

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_HOST: "10.10.10.30",
    CONF_NAME: "NZBGetTest",
    CONF_PASSWORD: "",
    CONF_PORT: 6789,
    CONF_SSL: False,
    CONF_USERNAME: "",
    CONF_VERIFY_SSL: False,
}

ENTRY_OPTIONS = {CONF_SCAN_INTERVAL: 5}

USER_INPUT = {
    CONF_HOST: "10.10.10.30",
    CONF_NAME: "NZBGet",
    CONF_PASSWORD: "",
    CONF_PORT: 6789,
    CONF_SSL: False,
    CONF_USERNAME: "",
}

MOCK_VERSION = "21.0"

MOCK_STATUS = {
    "ArticleCacheMB": 64,
    "AverageDownloadRate": 1250000,
    "DownloadPaused": False,
    "DownloadRate": 2500000,
    "DownloadedSizeMB": 256,
    "FreeDiskSpaceMB": 1024,
    "PostJobCount": 2,
    "PostPaused": False,
    "RemainingSizeMB": 512,
    "UpTimeSec": 600,
    "DownloadLimit": 1000000,
}

MOCK_HISTORY = [
    {"Name": "Downloaded Item XYZ", "Category": "", "Status": "SUCCESS"},
    {"Name": "Failed Item ABC", "Category": "", "Status": "FAILURE"},
]


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the NZBGet integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG, options=ENTRY_OPTIONS)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.nzbget.async_setup_entry",
        return_value=return_value,
    )


def _patch_history():
    return patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.history",
        return_value=MOCK_HISTORY,
    )


def _patch_status():
    return patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.status",
        return_value=MOCK_STATUS,
    )


def _patch_version(return_value=MOCK_VERSION):
    return patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.version",
        return_value=return_value,
    )
