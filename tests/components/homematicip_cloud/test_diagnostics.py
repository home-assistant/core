"""Tests for HomematicIP Cloud diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homematicip_cloud.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

MOCK_CONFIG = {
    "accessPointId": "3014F7110000000000000001",
    "home": {
        "id": "a1b2c3d4-e5f6-1234-abcd-ef0123456789",
        "location": {
            "city": "Berlin, Germany",
            "latitude": "52.520008",
            "longitude": "13.404954",
        },
        "weather": {"temperature": 18.3},
    },
    "devices": {
        "3014F7110000000000000002": {
            "id": "3014F7110000000000000002",
            "label": "Living Room Thermostat",
            "type": "WALL_MOUNTED_THERMOSTAT_PRO",
            "serializedGlobalTradeItemNumber": "ABCDEFGHIJKLMNOPQRSTUVWX",
        }
    },
    "clients": {
        "a1b2c3d4-e5f6-1234-abcd-ef0123456789": {
            "id": "a1b2c3d4-e5f6-1234-abcd-ef0123456789",
            "label": "Home Assistant",
            "refreshToken": "secret-refresh-token",
        }
    },
}


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_hap_with_service,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    mock_hap_with_service.home.download_configuration_async.return_value = MOCK_CONFIG

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
