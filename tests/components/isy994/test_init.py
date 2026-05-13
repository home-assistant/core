"""Test the Universal Devices ISY/IoX integration init."""

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_UUID = "ce:fb:72:31:b7:b9"


async def test_migrate_minor_version_drops_tls(
    hass: HomeAssistant,
) -> None:
    """Test minor migration drops legacy "tls" and seeds verify_ssl."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            "tls": 1.1,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert "tls" not in entry.data
    assert entry.data[CONF_VERIFY_SSL] is False
