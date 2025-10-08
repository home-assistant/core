"""Test for airOS integration setup."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock

from homeassistant.components.airos.const import (
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SECTION_ADVANCED_SETTINGS,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    SECTION_ADVANCED_SETTINGS: {
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    },
}

MOCK_CONFIG_V1_2 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    SECTION_ADVANCED_SETTINGS: {
        CONF_SSL: DEFAULT_SSL,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    },
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

    assert mock_config_entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL] is True
    assert mock_config_entry.data[SECTION_ADVANCED_SETTINGS][CONF_VERIFY_SSL] is False


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
        minor_version=2,
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

    assert entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL] is False
    assert entry.data[SECTION_ADVANCED_SETTINGS][CONF_VERIFY_SSL] is False


async def test_ssl_migrate_entry(
    hass: HomeAssistant, mock_airos_client: MagicMock
) -> None:
    """Test migrate entry SSL options."""
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
    assert entry.minor_version >= 2
    assert entry.data == MOCK_CONFIG_V1_2


async def test_uid_migrate_entry(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migrate entry unique id."""
    entity_registry = er.async_get(hass)

    MOCK_MAC = dr.format_mac("01:23:45:67:89:AB")
    MOCK_ID = "device_id_12345"
    old_unique_id = f"{MOCK_ID}_port_forwarding"
    new_unique_id = f"{MOCK_MAC}_port_forwarding"

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id=MOCK_ID,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_ID)},
        connections={
            (dr.CONNECTION_NETWORK_MAC, MOCK_MAC),
        },
    )
    await hass.async_block_till_done()

    old_entity_entry = entity_registry.async_get_or_create(
        DOMAIN, BINARY_SENSOR_DOMAIN, old_unique_id, config_entry=entry
    )
    original_entity_id = old_entity_entry.entity_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    updated_entity_entry = entity_registry.async_get(original_entity_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 0
    assert (
        entity_registry.async_get_entity_id(BINARY_SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
    assert updated_entity_entry.unique_id == new_unique_id


async def test_uid_migrate_entry_fail(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migrate entry unique id failure for mac address unknown."""
    MOCK_ID = "device_id_12345"

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id=MOCK_ID,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_ID)},
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert entry.minor_version == 2


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
        version=3,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup and unload config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
