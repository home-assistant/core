"""Tests for the OctoPrint integration."""
from unittest.mock import patch

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.components.octoprint import DOMAIN
from homeassistant.setup import async_setup_component

DEFAULT_JOB = {
    "job": {},
    "progress": {"completion": 50},
}

DEFAULT_PRINTER = {
    "state": {
        "flags": {"printing": True, "error": False},
        "text": "Operational",
    },
    "temperature": [],
}


async def init_integration(
    hass, platform, printer: dict = DEFAULT_PRINTER, job: dict = DEFAULT_JOB
):
    """Set up the octoprint integration in Home Assistant."""
    config = {
        DOMAIN: {
            "host": "192.168.1.5",
            "api_key": "test-key",
            "ssl": False,
            "port": 80,
            "path": "/",
            "name": "Octoprint",
        }
    }
    with patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(printer),
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_job_info",
        return_value=OctoprintJobInfo(job),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
