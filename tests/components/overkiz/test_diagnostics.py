"""Tests for the diagnostics data provided by the Overkiz integration."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    info = {
        "hz_actual": (3200000001, 0),
        "arch_string_raw": "aargh",
        "brand_raw": "Intel Ryzen 7",
        "hz_advertised": (3600000001, 0),
    }

    with patch(
        "pyoverkiz.client.OverkizClient.get_diagnostic_data",
        return_value=info,
    ):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
            == snapshot
        )
