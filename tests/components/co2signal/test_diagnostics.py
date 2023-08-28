"""Test the CO2Signal diagnostics."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.co2signal import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import VALID_PAYLOAD

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "api_key", "location": ""},
        entry_id="904a74160aa6f335526706bee85dfb83",
    )
    config_entry.add_to_hass(hass)
    with patch("CO2Signal.get_latest", return_value=VALID_PAYLOAD):
        assert await async_setup_component(hass, DOMAIN, {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
