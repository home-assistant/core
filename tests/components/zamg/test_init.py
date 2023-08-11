"""Test Zamg component init."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN as ZAMG_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_CONFIG_ENTRY
from .conftest import (
    TEST_STATION_ID,
    TEST_STATION_ID_2,
    TEST_STATION_NAME,
    TEST_STATION_NAME_2,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id", "station_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": f"{TEST_STATION_NAME}_{TEST_STATION_ID}",
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            f"{TEST_STATION_NAME}_{TEST_STATION_ID}",
            TEST_STATION_ID,
            TEST_STATION_ID,
        ),
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": f"{TEST_STATION_NAME_2}_{TEST_STATION_ID_2}",
                "suggested_object_id": f"Zamg {TEST_STATION_NAME_2}",
                "disabled_by": None,
            },
            f"{TEST_STATION_NAME_2}_{TEST_STATION_ID_2}",
            TEST_STATION_ID_2,
            TEST_STATION_ID_2,
        ),
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": f"{TEST_STATION_NAME_2}_{TEST_STATION_ID_2}_temperature",
                "suggested_object_id": f"Zamg {TEST_STATION_NAME_2}",
                "disabled_by": None,
            },
            f"{TEST_STATION_NAME_2}_{TEST_STATION_ID_2}_temperature",
            f"{TEST_STATION_NAME_2}_{TEST_STATION_ID_2}_temperature",
            TEST_STATION_ID_2,
        ),
    ],
)
async def test_migrate_unique_ids(
    hass: HomeAssistant,
    mock_zamg_coordinator: MagicMock,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    station_id: str,
) -> None:
    """Test successful migration of entity unique_ids."""
    FIXTURE_CONFIG_ENTRY["data"][CONF_STATION_ID] = station_id
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id", "station_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": f"{TEST_STATION_NAME}_{TEST_STATION_ID}",
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            f"{TEST_STATION_NAME}_{TEST_STATION_ID}",
            TEST_STATION_ID,
            TEST_STATION_ID,
        ),
    ],
)
async def test_dont_migrate_unique_ids(
    hass: HomeAssistant,
    mock_zamg_coordinator: MagicMock,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    station_id: str,
) -> None:
    """Test successful migration of entity unique_ids."""
    FIXTURE_CONFIG_ENTRY["data"][CONF_STATION_ID] = station_id
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    # create existing entry with new_unique_id
    existing_entity = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        ZAMG_DOMAIN,
        unique_id=TEST_STATION_ID,
        suggested_object_id=f"Zamg {TEST_STATION_NAME}",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == old_unique_id

    entity_not_changed = entity_registry.async_get(existing_entity.entity_id)
    assert entity_not_changed
    assert entity_not_changed.unique_id == new_unique_id

    assert entity_migrated != entity_not_changed


@pytest.mark.parametrize(
    ("entitydata", "unique_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": TEST_STATION_ID,
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            TEST_STATION_ID,
        ),
    ],
)
async def test_unload_entry(
    hass: HomeAssistant,
    mock_zamg_coordinator: MagicMock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test unload entity unique_ids."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        ZAMG_DOMAIN,
        unique_id=TEST_STATION_ID,
        suggested_object_id=f"Zamg {TEST_STATION_NAME}",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(unique_id) is None
