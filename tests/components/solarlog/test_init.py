"""Test the initialization."""

from homeassistant.components.solarlog.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .test_config_flow import HOST, NAME

from tests.common import MockConfigEntry


async def test_migrate_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={
            CONF_HOST: HOST,
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert entry.version == 1
    assert entry.minor_version == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_HOST] == HOST
    assert entry.data["extended_data"] is False
