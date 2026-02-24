"""Tests for HomematicIP Cloud diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homematicip_cloud.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import async_load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_hap_with_service,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    mock_hap_with_service.home.download_configuration_async.return_value = (
        await async_load_json_object_fixture(hass, "diagnostics.json", DOMAIN)
    )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
