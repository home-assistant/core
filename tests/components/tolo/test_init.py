"""Tests for TOLO __init__ module."""

from homeassistant.components.tolo import CONF_ACCESSORIES, CONF_EXPERT
from homeassistant.components.tolo.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test TOLO config entry migration."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        entry_id="1",
        version=1,
        minor_version=1,
        title="TOLO Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert CONF_ACCESSORIES in entry.data
    assert CONF_EXPERT in entry.data
