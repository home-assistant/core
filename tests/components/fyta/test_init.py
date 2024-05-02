"""Test the initialization."""

from unittest.mock import AsyncMock

from homeassistant.components.fyta.const import CONF_EXPIRATION, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .test_config_flow import ACCESS_TOKEN, PASSWORD, USERNAME

from tests.common import MockConfigEntry


async def test_migrate_config_entry(
    hass: HomeAssistant,
    mock_fyta_init: AsyncMock,
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
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
    assert entry.data[CONF_USERNAME] == USERNAME
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.data[CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert entry.data[CONF_EXPIRATION] == "2024-12-31T10:00:00+00:00"
