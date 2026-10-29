"""Tests for diagnostics data."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "device_fixture",
    [
        "HWE-P1",
        "HWE-SKT-11",
        "HWE-SKT-21",
        "HWE-WTR",
        "SDM230",
        "SDM630",
        "HWE-KWH1",
        "HWE-KWH3",
        "HWE-BAT",
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
