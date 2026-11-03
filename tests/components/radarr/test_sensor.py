"""The tests for Radarr sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from aiopyarr.exceptions import ArrConnectionException
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.radarr.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import mock_calendar, mock_connection, setup_integration


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
@pytest.mark.parametrize(
    ("windows", "single", "root_folder"),
    [
        (
            False,
            False,
            "downloads",
        ),
        (
            False,
            True,
            "downloads",
        ),
        (
            True,
            False,
            "tv",
        ),
        (
            True,
            True,
            "tv",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    windows: bool,
    single: bool,
    root_folder: str,
) -> None:
    """Test for successfully setting up the Radarr platform."""
    await setup_integration(hass, aioclient_mock, windows=windows, single_return=single)

    state = hass.states.get(f"sensor.mock_title_disk_space_{root_folder}")
    assert state.state == "263.10"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    state = hass.states.get("sensor.mock_title_movies")
    assert state.state == "2"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "movies"
    state = hass.states.get("sensor.mock_title_start_time")
    assert state.state == "2020-09-01T23:50:20+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.mock_title_queue")
    assert state.state == "2"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "movies"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
async def test_windows(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test for successfully setting up the Radarr platform on Windows."""
    await setup_integration(hass, aioclient_mock, windows=True)

    state = hass.states.get("sensor.mock_title_disk_space_tv")
    assert state.state == "263.10"


@pytest.mark.parametrize(
    ("root_folder_fixture", "expected"),
    [
        pytest.param(
            "rootfolder-duplicate-names",
            {1: "263.10", 2: "93.13"},
            id="linux_duplicate_names",
        ),
        pytest.param(
            "rootfolder-duplicate-names-windows",
            {1: "263.10", 2: "93.13"},
            id="windows_duplicate_names",
        ),
        pytest.param(
            "rootfolder-overlapping-names",
            {1: "93.13", 2: "263.10"},
            id="overlapping_names",
        ),
        pytest.param(
            "rootfolder-similar-paths",
            {1: "263.10", 2: "93.13", 3: "46.57"},
            id="similar_paths",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_root_folder_names(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    root_folder_fixture: str,
    expected: dict[int, str],
) -> None:
    """Test each root folder gets its own disk space sensor and free space."""
    entry = await setup_integration(
        hass, aioclient_mock, root_folder_fixture=root_folder_fixture
    )

    for folder_id, free_space in expected.items():
        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{entry.entry_id}_root_folder_{folder_id}_disk_space",
        )
        assert hass.states.get(entity_id).state == free_space
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migrate_folder_name_unique_id(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a folder name unique ID migrates to the first root folder with that name."""
    entry = await setup_integration(
        hass,
        aioclient_mock,
        root_folder_fixture="rootfolder-duplicate-names",
        skip_entry_setup=True,
    )
    entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{entry.entry_id}_disk_space_Movies",
        config_entry=entry,
        suggested_object_id="mock_title_disk_space_movies",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated = entity_registry.async_get(entity.entity_id)
    assert migrated.unique_id == f"{entry.entry_id}_root_folder_1_disk_space"
    assert hass.states.get(entity.entity_id).state == "263.10"


@pytest.mark.parametrize(
    "root_folder_fixture",
    [
        pytest.param("rootfolder-added", id="folder_added"),
        pytest.param("rootfolder-removed-first", id="folder_removed"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_root_folder_changes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    root_folder_fixture: str,
) -> None:
    """Test adding or removing a root folder keeps the other sensors unchanged."""
    entry = await setup_integration(
        hass, aioclient_mock, root_folder_fixture="rootfolder-duplicate-names"
    )
    unique_id = f"{entry.entry_id}_root_folder_2_disk_space"
    entity_id = entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert hass.states.get(entity_id).state == "93.13"

    aioclient_mock.clear_requests()
    mock_connection(aioclient_mock, root_folder_fixture=root_folder_fixture)
    mock_calendar(aioclient_mock)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
        == entity_id
    )
    assert hass.states.get(entity_id).state == "93.13"


async def test_update_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test coordinator updates handle failures."""
    entry = await setup_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.LOADED
    entity = "sensor.mock_title_disk_space_downloads"
    assert hass.states.get(entity).state == "263.10"

    with patch(
        "homeassistant.components.radarr.RadarrClient._async_request",
        side_effect=ArrConnectionException,
    ) as updater:
        next_update = dt_util.utcnow() + timedelta(minutes=1)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        assert updater.call_count == 2
        assert hass.states.get(entity).state == STATE_UNAVAILABLE

    next_update = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "263.10"
