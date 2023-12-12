"""Test the BraviaTV diagnostics."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.braviatv.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            "mac": "AA:BB:CC:DD:EE:FF",
            "use_psk": True,
            "pin": "12345qwerty",
        },
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
    )

    config_entry.add_to_hass(hass)
    with patch("pybravia.BraviaClient.connect"), patch(
        "pybravia.BraviaClient.pair"
    ), patch("pybravia.BraviaClient.set_wol_mode"), patch(
        "pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot
