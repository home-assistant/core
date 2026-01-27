"""Tests for the OctoPrint integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

from pyoctoprintapi import (
    DiscoverySettings,
    OctoprintJobInfo,
    OctoprintPrinterInfo,
    TrackingSetting,
    WebcamSettings,
)
import pytest

from homeassistant.components.octoprint import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import DEFAULT_JOB, DEFAULT_PRINTER

from tests.common import MockConfigEntry


@pytest.fixture
def job() -> dict[str, Any]:
    """Job fixture."""
    return DEFAULT_JOB


@pytest.fixture
def printer() -> dict[str, Any]:
    """Printer fixture."""
    return DEFAULT_PRINTER


@pytest.fixture
def webcam() -> dict[str, Any] | None:
    """Webcam fixture."""
    return None


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    platform: Platform,
    printer: dict[str, Any] | None,
    job: dict[str, Any],
    webcam: dict[str, Any] | None,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the octoprint integration in Home Assistant."""
    printer_info: OctoprintPrinterInfo | None = None
    if printer is not None:
        printer_info = OctoprintPrinterInfo(printer)
    webcam_info: WebcamSettings | None = None
    if webcam is not None:
        webcam_info = WebcamSettings(**webcam)
    with (
        patch("homeassistant.components.octoprint.PLATFORMS", [platform]),
        patch("pyoctoprintapi.OctoprintClient.get_server_info", return_value={}),
        patch(
            "pyoctoprintapi.OctoprintClient.get_printer_info",
            return_value=printer_info,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_job_info",
            return_value=OctoprintJobInfo(job),
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_tracking_info",
            return_value=TrackingSetting({"unique_id": "uuid"}),
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_webcam_info",
            return_value=webcam_info,
        ),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "OctoPrint",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
            title="OctoPrint",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        yield config_entry
