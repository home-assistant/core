"""ESPHome set up tests."""

import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_zeroconf")
async def test_delete_entry(hass: HomeAssistant, mock_client) -> None:
    """Test we can delete an entry with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
