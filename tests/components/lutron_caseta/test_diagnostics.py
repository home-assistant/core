"""Test the Lutron Caseta diagnostics."""

from unittest.mock import patch

from homeassistant.components.lutron_caseta import DOMAIN
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
)
from homeassistant.const import CONF_HOST

from . import MockBridge

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass, hass_client) -> None:
    """Test generating diagnostics for lutron_caseta."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_KEYFILE: "",
            CONF_CERTFILE: "",
            CONF_CA_CERTS: "",
        },
        unique_id="abc",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls",
        return_value=MockBridge(can_connect=True),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert "entry" in diag
    assert "bridge_data" in diag
    assert "integration_data" in diag
