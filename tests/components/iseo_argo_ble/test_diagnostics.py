"""Test the ISEO Argo BLE diagnostics platform."""

from unittest.mock import patch

from homeassistant.components.iseo_argo_ble.const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_UUID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, setup_test_component_platform
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_UUID: "1234567890abcdef1234567890abcdef",
            CONF_PRIV_SCALAR: "deadbeef",
        },
        title="Mock Title",
    )
    entry.add_to_hass(hass)

    # Diagnostics platform needs to be registered.
    # In a real setup, async_setup_entry forwards to diagnostics platform.
    # Here we just need diagnostics to be loaded for the domain.
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", ["diagnostics"]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag["config_entry_data"][CONF_ADDRESS] == "aa:bb:cc:dd:ee:ff"
    assert diag["config_entry_data"][CONF_UUID] == "**REDACTED**"
    assert diag["config_entry_data"][CONF_PRIV_SCALAR] == "**REDACTED**"
