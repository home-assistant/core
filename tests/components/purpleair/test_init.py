"""PurpleAir init flow tests."""

from homeassistant.components.purpleair import async_migrate_entry
from homeassistant.components.purpleair.const import (
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    DOMAIN,
    SCHEMA_VERSION,
    TITLE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from .const import (
    TEST_API_KEY,
    TEST_NEW_API_KEY,
    TEST_SENSOR_INDEX1,
    TEST_SENSOR_INDEX2,
)

from tests.common import MockConfigEntry, mock_device_registry


async def test_load_unload(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """Test load and unload."""

    # Already loaded by setup_config_entry mock
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant,
) -> None:
    """Test migrate entry to new schema."""

    # Create v1 config entries
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            "sensor_indices": [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: True,
        },
        title="1234",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_NEW_API_KEY},
        options={
            "sensor_indices": [TEST_SENSOR_INDEX2],
            CONF_SHOW_ON_MAP: False,
        },
        title="5678",
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)
    await hass.async_block_till_done()

    # Created devices
    dr = mock_device_registry(hass)
    dr.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    dr.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    await hass.async_block_till_done()

    # Migrate from v1 to v2
    assert await async_migrate_entry(hass, entry1) is True
    await hass.async_block_till_done()
    assert await async_migrate_entry(hass, entry2) is True
    await hass.async_block_till_done()

    # Verify config entry
    assert entry1.title == f"{TITLE} (1234)"
    assert entry2.title == f"{TITLE} (5678)"
    assert entry1.unique_id == TEST_API_KEY
    assert entry2.unique_id == TEST_NEW_API_KEY
    assert entry1.version == SCHEMA_VERSION
    assert entry2.version == SCHEMA_VERSION
    assert entry1.data == {CONF_API_KEY: TEST_API_KEY}
    assert entry2.data == {CONF_API_KEY: TEST_NEW_API_KEY}
    assert entry1.options == {CONF_SHOW_ON_MAP: True}
    assert entry2.options == {CONF_SHOW_ON_MAP: False}

    # Verify subentries
    assert len(entry1.subentries) == 1
    assert len(entry2.subentries) == 1

    subentry = next(
        (
            subentry
            for subentry in entry1.subentries.values()
            if subentry.unique_id == str(TEST_SENSOR_INDEX1)
        ),
        None,
    )
    assert subentry is not None
    assert subentry.subentry_type == CONF_SENSOR
    assert subentry.title == f"TEST_SENSOR_INDEX1 ({TEST_SENSOR_INDEX1})"
    assert subentry.unique_id == str(TEST_SENSOR_INDEX1)
    assert subentry.data == {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1}

    subentry = next(
        (
            subentry
            for subentry in entry2.subentries.values()
            if subentry.unique_id == str(TEST_SENSOR_INDEX2)
        ),
        None,
    )
    assert subentry is not None
    assert subentry.subentry_type == CONF_SENSOR
    assert subentry.title == f"TEST_SENSOR_INDEX2 ({TEST_SENSOR_INDEX2})"
    assert subentry.unique_id == str(TEST_SENSOR_INDEX2)
    assert subentry.data == {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2}


async def test_migrate_entry_current_schema(
    hass: HomeAssistant,
) -> None:
    """Test migrate entry with the current schema."""

    # Try to migrate current schema
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()
    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()


async def test_migrate_entry_unknown_schema(
    hass: HomeAssistant,
) -> None:
    """Test migrate entry with unknown schema."""

    # Try to migrate unknown schema
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=10,
        data={},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()
    assert await async_migrate_entry(hass, entry) is not True
    await hass.async_block_till_done()


async def test_migrate_entry_no_sensors(
    hass: HomeAssistant,
) -> None:
    """Test migrate entry with no v1 sensors."""

    # Try to migrate with no v1 sensors
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()
    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()
