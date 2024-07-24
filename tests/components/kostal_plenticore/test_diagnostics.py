"""Test Kostal Plenticore diagnostics."""

from pykoplenti import SettingsData
from syrupy import SnapshotAssertion

from homeassistant.components.kostal_plenticore.coordinator import Plenticore
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_plenticore: Plenticore,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    # set some test process and settings data for the diagnostics output
    mock_plenticore.client.get_process_data.return_value = {
        "devices:local": ["HomeGrid_P", "HomePv_P"]
    }

    mock_plenticore.client.get_settings.return_value = {
        "devices:local": [
            SettingsData(
                min="5",
                max="100",
                default=None,
                access="readwrite",
                unit="%",
                id="Battery:MinSoc",
                type="byte",
            )
        ]
    }

    await snapshot_get_diagnostics_for_config_entry(
        hass, hass_client, init_integration, snapshot
    )
