"""Test Blink diagnostics."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
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

    await snapshot_get_diagnostics_for_config_entry(
        hass, hass_client, mock_entry, snapshot
    )
