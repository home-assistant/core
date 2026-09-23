"""Test the Bravia TV integration setup."""

from unittest.mock import patch

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_DATA = {
    CONF_HOST: "bravia-host",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_PIN: "secret",
    CONF_USE_PSK: True,
}


async def test_migrate_empty_unique_id(hass: HomeAssistant) -> None:
    """Test an entry stored without a CID adopts the MAC as unique ID."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="", data=ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.BraviaClient", autospec=True),
        patch(
            "homeassistant.components.braviatv.coordinator.BraviaTVCoordinator._async_update_data",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_existing_unique_id_is_kept(hass: HomeAssistant) -> None:
    """Test an entry that already has a unique ID is left alone."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="very_unique_string", data=ENTRY_DATA
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.BraviaClient", autospec=True),
        patch(
            "homeassistant.components.braviatv.coordinator.BraviaTVCoordinator._async_update_data",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.unique_id == "very_unique_string"
