"""Init tests for the Telegram Bot integration."""

from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    CONF_ALLOWED_CHAT_IDS,
    CONF_API_ENDPOINT,
    CONF_CHAT_ID,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PARSER_MD,
    PLATFORM_BROADCAST,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_migrate_notify_entity_unique_id(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test migrate notify entity unique ID from chat ID to subentry ID."""
    subentry = ConfigSubentryData(
        unique_id="123456",
        data={CONF_CHAT_ID: 123456},
        subentry_type=CONF_ALLOWED_CHAT_IDS,
        title="mock chat",
    )
    mock_config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_ENDPOINT: DEFAULT_API_ENDPOINT,
            CONF_API_KEY: "mock api key",
        },
        options={ATTR_PARSER: PARSER_MD},
        subentries_data=[subentry],
        minor_version=2,
    )
    mock_config_entry.add_to_hass(hass)
    subentry_id = next(iter(mock_config_entry.subentries))
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "notify",
        DOMAIN,
        "123456_123456",
        suggested_object_id="legacy_telegram_notify",
        config_entry=mock_config_entry,
        config_subentry_id=subentry_id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry_entry = entity_registry.async_get("notify.legacy_telegram_notify")
    assert registry_entry is not None
    assert registry_entry.unique_id == f"123456_{subentry_id}"
    assert registry_entry.config_subentry_id == subentry_id
