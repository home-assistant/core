"""Test UniFi Protect diagnostics."""

import re
from typing import Any
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from uiprotect.data import Light

from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Pattern for hex IDs (24 char hex strings like device/user IDs)
HEX_ID_PATTERN = re.compile(r"^[a-f0-9]{24}$")
# Pattern for MAC addresses (12 hex chars)
MAC_PATTERN = re.compile(r"^[A-F0-9]{12}$")


def _normalize_diagnostics(data: Any) -> Any:
    """Normalize diagnostics data for deterministic snapshots.

    Removes repr fields (contain memory addresses) and normalizes
    hex IDs and MAC addresses that are randomly generated.
    """
    if isinstance(data, dict):
        return {
            k: _normalize_diagnostics(v)
            for k, v in data.items()
            if k != "repr"  # Remove repr fields with memory addresses
        }
    if isinstance(data, list):
        return [_normalize_diagnostics(item) for item in data]
    if isinstance(data, str):
        if HEX_ID_PATTERN.match(data):
            return "**REDACTED_ID**"
        if MAC_PATTERN.match(data):
            return "**REDACTED_MAC**"
    return data


async def test_diagnostics(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    await init_entry(hass, ufp, [light])

    # Mock anonymize_data to return unchanged data for deterministic snapshots
    with patch(
        "homeassistant.components.unifiprotect.diagnostics.anonymize_data",
        side_effect=lambda x: x,
    ):
        diag = await get_diagnostics_for_config_entry(hass, hass_client, ufp.entry)

    # Normalize data to remove non-deterministic values (memory addresses, random IDs)
    diag_normalized = _normalize_diagnostics(diag)

    assert diag_normalized == snapshot
