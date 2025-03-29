"""Test the Tado integration."""

from homeassistant.components.tado import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_v1_migration(hass: HomeAssistant) -> None:
    """Test migration from v1 to v2 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert CONF_USERNAME not in entry.data
    assert CONF_PASSWORD not in entry.data

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress()) == 1
