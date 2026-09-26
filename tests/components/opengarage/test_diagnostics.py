"""Test redacted OpenGarage diagnostics."""

from unittest.mock import MagicMock

from opengarage.state import normalize_state
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Include capability details without identifiers, keys, or malformed raw text."""
    mock_opengarage.get_state.return_value = normalize_state(
        {
            **mock_opengarage.get_state.return_value.raw,
            "secv": 1,
            "has_swrx": 1,
            "pemu": 2,
            "dkey": "secret",
            "device_key": "secret",
            "cid": 123,
            "_raw": "sensitive malformed response",
        }
    )
    await init_integration.runtime_data.async_refresh()
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
