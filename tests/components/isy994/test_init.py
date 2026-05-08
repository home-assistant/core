"""Test the Universal Devices ISY/IoX integration init."""

from unittest.mock import MagicMock

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_UUID = "ce:fb:72:31:b7:b9"


async def test_migrate_v1_drops_tls(
    hass: HomeAssistant,
    mock_isy: MagicMock,
) -> None:
    """Test that the v1 → v2 migration silently drops the legacy "tls" key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
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
    assert entry.version == 2
    assert "tls" not in entry.data
    assert CONF_VERIFY_SSL not in entry.data


async def test_migrate_future_version_fails(
    hass: HomeAssistant,
    mock_isy: MagicMock,
) -> None:
    """Test that migrating from a future version is not possible."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
