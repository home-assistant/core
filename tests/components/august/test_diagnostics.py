"""Test august diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .mocks import (
    _create_august_api_with_devices,
    _mock_doorbell_from_fixture,
    _mock_lock_from_fixture,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    lock_one = await _mock_lock_from_fixture(
        hass, "get_lock.online_with_doorsense.json"
    )
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")

    entry, _ = await _create_august_api_with_devices(hass, [lock_one, doorbell_one])
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == snapshot
