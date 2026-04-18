"""Init tests for the Telegram Bot integration."""

from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    CONF_API_ENDPOINT,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PARSER_MD,
    PLATFORM_BROADCAST,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migration_error(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test migrate config entry from 1.1 to 1.2."""

    mock_config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "mock api key",
        },
        options={ATTR_PARSER: PARSER_MD},
        version=99,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_from_1_1(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test migrate config entry from 1.1 to 1.2."""

    mock_config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "mock api key",
        },
        options={ATTR_PARSER: PARSER_MD},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 2
    assert mock_config_entry.data == {
        CONF_PLATFORM: PLATFORM_BROADCAST,
        CONF_API_KEY: "mock api key",
        CONF_API_ENDPOINT: DEFAULT_API_ENDPOINT,
    }
