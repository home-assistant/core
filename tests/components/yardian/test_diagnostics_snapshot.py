"""Snapshot diagnostics test for Yardian."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pyyardian.async_client import YardianDeviceState

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.components.yardian.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class FakeYardianClient:
    """Fake client for diagnostics snapshot tests."""

    def __init__(self, *_: object, **__: object) -> None:
        """Initialize fake client."""

    async def fetch_device_state(self):
        """Return fake device state for snapshot tests."""
        zones = [["Zone 1", 1], ["Zone 2", 0], ["Zone 3", 1]]
        active_zones = {0}
        return YardianDeviceState(zones=zones, active_zones=active_zones)

    async def fetch_oper_info(self):
        """Return fake operation info for snapshot tests."""
        return {
            "iRainDelay": 3600,
            "iStandby": 0,
            "fFreezePrevent": 1,
            "iSensorDelay": 5,
            "iWaterHammerDuration": 2,
            "region": "US",
        }


@pytest.mark.asyncio
async def test_diagnostics_snapshot(hass: HomeAssistant) -> None:
    """Validate diagnostics payload shape and redaction without snapshots."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "access_token": "token123",
            "name": "Yardian",
            "yid": "yid123",
            "model": "PRO1902",
            "serialNumber": "SN1",
        },
        title="Yardian Smart Sprinkler",
        unique_id="yid123",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "device" in diag and "state" in diag and "oper_info" in diag
    assert diag["device"]["name"] == "Yardian Smart Sprinkler"
    assert diag["device"]["yid"] == "**REDACTED**"
    assert isinstance(diag["state"]["active_zones"], list)
    assert isinstance(diag["state"]["zones"], list)
    assert diag["oper_info"]["region"] == "US"
