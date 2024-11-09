"""Test Blink diagnostics."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

YAML_CONFIG = {"username": "test-user", "password": "test-password"}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_appliances_manager_api: MagicMock,
    mock_aircon1_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test config entry diagnostics."""

    mock_entry = await init_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert result == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
