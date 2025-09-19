"""Test diagnostics for Yardian."""

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
    """Fake client returning deterministic diagnostics data."""

    def __init__(self, *_: object, **__: object) -> None:
        """Initialize fake client."""

    async def fetch_device_state(self):
        """Return fake device state for diagnostics tests."""
        zones = [["Zone 1", 1], ["Zone 2", 0]]
        active_zones: set[int] = set()
        return YardianDeviceState(zones=zones, active_zones=active_zones)

    async def fetch_oper_info(self):
        """Return fake operation info for diagnostics tests."""
        return {
            "iRainDelay": 0,
            "iStandby": 0,
            "fFreezePrevent": 0,
            "sIotcUid": "secret",
            "region": "US",
        }


@pytest.mark.asyncio
async def test_diagnostics_redaction(hass: HomeAssistant) -> None:
    """Test diagnostics data is returned and redacted."""

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

    # Ensure keys exist
    assert (
        "entry" in diag and "device" in diag and "state" in diag and "oper_info" in diag
    )
    # Redacted sensitive fields (new redaction style uses **REDACTED**)
    redacted = "**REDACTED**"
    assert diag["entry"]["data"]["host"] == redacted
    assert diag["entry"]["data"]["access_token"] == redacted
    assert diag["device"]["yid"] == redacted
    assert diag["oper_info"]["sIotcUid"] == redacted
