"""Test Schlage diagnostics."""

from unittest.mock import Mock

from pytest_homeassistant.common import async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.schlage.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_lock: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Schlage diagnostics."""
    # Lock.get_diagnostics() output for the wifi_lock_json fixture in pyschlage's
    # own tests, generated with pyschlage 2026.11.0.
    mock_lock.get_diagnostics.return_value = await async_load_json_object_fixture(
        hass, "lock_diagnostics.json", DOMAIN
    )
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    )
    assert diag == snapshot
