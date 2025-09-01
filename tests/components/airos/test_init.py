"""Test for airOS integration setup."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock

from homeassistant.components.airos.const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG_V1 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
}

MOCK_CONFIG_PLAIN = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    CONF_SSL: False,
}

MOCK_CONFIG_V1_2 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}


async def test_setup_entry_with_default_ssl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airos_client: MagicMock,
    mock_airos_class: MagicMock,
) -> None:
    """Test setting up a config entry with default SSL options."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_airos_class.assert_called_once_with(
        host=mock_config_entry.data[CONF_HOST],
        username=mock_config_entry.data[CONF_USERNAME],
        password=mock_config_entry.data[CONF_PASSWORD],
        session=ANY,
        use_ssl=DEFAULT_SSL,
    )

    assert mock_config_entry.data[CONF_SSL] is True
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False


async def test_setup_entry_without_ssl(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    mock_airos_class: MagicMock,
) -> None:
    """Test setting up a config entry adjusted to plain HTTP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_PLAIN,
        entry_id="1",
        unique_id="airos_device",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    mock_airos_class.assert_called_once_with(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=ANY,
        use_ssl=False,
    )

    assert entry.data[CONF_SSL] is False
    assert entry.data[CONF_VERIFY_SSL] is False


async def test_migrate_entry(hass: HomeAssistant, mock_airos_client: MagicMock) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1,
        entry_id="1",
        unique_id="airos_device",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == MOCK_CONFIG_V1_2


async def test_migrate_future_return(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id="airos_device",
        version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_load_unload_entry(
    hass: HomeAssistant, mock_airos_client: MagicMock
) -> None:
    """Test setup and unload config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id="airos_device",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
