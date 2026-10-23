"""Test automatic Home Assistant updates."""

from dataclasses import replace
from datetime import time, timedelta
import os
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import UpdateChannel
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.auto_update import (
    AUTO_UPDATE_OPTIONS_SCHEMA,
    AutoUpdateSettings,
    AutoUpdateUnavailableReason,
)
from homeassistant.components.hassio.const import (
    DATA_AUTO_UPDATE,
    HASSIO_MAIN_UPDATE_INTERVAL,
)
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}
STORAGE_KEY = "hassio.auto_update"


@pytest.fixture(autouse=True)
def mock_all(
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_stats: AsyncMock,
    addon_changelog: AsyncMock,
    resolution_info: AsyncMock,
    jobs_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    homeassistant_info: AsyncMock,
    supervisor_info: AsyncMock,
    addons_list: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
    homeassistant_stats: AsyncMock,
    supervisor_stats: AsyncMock,
    ingress_panels: AsyncMock,
) -> None:
    """Mock all setup requests, running 2026.10.1 with 2026.10.2 offered."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value,
        version="2026.10.1",
        version_latest="2026.10.2",
        update_available=True,
    )


async def _setup_hassio(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Set up the hassio integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, options=options or {}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(hass, DOMAIN, {"hassio": {}})
        await hass.async_block_till_done()

    return config_entry


async def test_default_settings(hass: HomeAssistant) -> None:
    """Test the settings when the user has not chosen anything yet."""
    await _setup_hassio(hass)

    assert hass.data[DATA_AUTO_UPDATE].settings == AutoUpdateSettings(
        enabled=None,
        delay=timedelta(days=3),
        window_start=time(3, 0),
        window_end=time(5, 0),
        weekdays=frozenset(WEEKDAYS),
    )


async def test_stored_settings(hass: HomeAssistant) -> None:
    """Test the settings are read from the config entry options."""
    await _setup_hassio(
        hass,
        {
            "core_auto_update": True,
            "core_auto_update_delay": 7,
            "core_auto_update_window_start": "23:00:00",
            "core_auto_update_window_end": "01:00:00",
            "core_auto_update_weekdays": ["sat", "sun"],
        },
    )

    assert hass.data[DATA_AUTO_UPDATE].settings == AutoUpdateSettings(
        enabled=True,
        delay=timedelta(days=7),
        window_start=time(23, 0),
        window_end=time(1, 0),
        weekdays=frozenset({"sat", "sun"}),
    )


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="empty"),
        pytest.param({"core_auto_update": False}, id="disabled"),
        pytest.param({"core_auto_update_delay": 0}, id="no_delay"),
        pytest.param(
            {
                "core_auto_update_window_start": "23:00",
                "core_auto_update_window_end": "01:00",
            },
            id="window_crosses_midnight",
        ),
        pytest.param({"core_auto_update_weekdays": ["mon"]}, id="one_weekday"),
    ],
)
def test_options_schema_valid(options: dict[str, Any]) -> None:
    """Test valid automatic update options."""
    AUTO_UPDATE_OPTIONS_SCHEMA(options)


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"core_auto_update_delay": 2}, id="unknown_delay"),
        pytest.param(
            {
                "core_auto_update_window_start": "03:00",
                "core_auto_update_window_end": "03:00",
            },
            id="empty_window",
        ),
        pytest.param(
            {"core_auto_update_window_start": "05:00"}, id="start_at_default_end"
        ),
        pytest.param(
            {"core_auto_update_window_end": "03:00"}, id="end_at_default_start"
        ),
        pytest.param({"core_auto_update_window_start": "25:00"}, id="invalid_time"),
        pytest.param({"core_auto_update_weekdays": []}, id="no_weekdays"),
        pytest.param({"core_auto_update_weekdays": ["someday"]}, id="unknown_weekday"),
    ],
)
def test_options_schema_invalid(options: dict[str, Any]) -> None:
    """Test invalid automatic update options are rejected."""
    with pytest.raises(probatio.Invalid):
        AUTO_UPDATE_OPTIONS_SCHEMA(options)


def test_options_schema_to_settings() -> None:
    """Test validated options can be read back as settings."""
    options = AUTO_UPDATE_OPTIONS_SCHEMA(
        {
            "core_auto_update_window_start": "23:00",
            "core_auto_update_window_end": "01:30",
        }
    )

    settings = AutoUpdateSettings.from_options(options)

    assert settings.window_start == time(23, 0)
    assert settings.window_end == time(1, 30)


async def _refresh_main_coordinator(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Let the main coordinator refresh on its schedule."""
    freezer.tick(HASSIO_MAIN_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_first_seen_is_set_once(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    homeassistant_info: AsyncMock,
) -> None:
    """Test the first time a version is offered is recorded and never changes."""
    first_seen = dt_util.utcnow()
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert manager.async_get_first_seen("2026.10.2") == first_seen

    await _refresh_main_coordinator(hass, freezer)

    assert manager.async_get_first_seen("2026.10.2") == first_seen

    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.3"
    )
    await _refresh_main_coordinator(hass, freezer)
    newer_first_seen = dt_util.utcnow()

    assert manager.async_get_first_seen("2026.10.2") == first_seen
    assert manager.async_get_first_seen("2026.10.3") == newer_first_seen

    assert hass_storage[STORAGE_KEY]["data"] == {
        "first_seen": {
            "2026.10.2": first_seen.isoformat(),
            "2026.10.3": newer_first_seen.isoformat(),
        },
        "skipped": [],
    }


async def test_first_seen_survives_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a reload right after a version is first seen keeps its time."""
    first_seen = dt_util.utcnow()
    config_entry = await _setup_hassio(hass)

    freezer.tick(timedelta(seconds=1))
    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DATA_AUTO_UPDATE].async_get_first_seen("2026.10.2") == first_seen


async def test_first_seen_survives_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test stored first-seen times are kept and older majors are dropped."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {
            "first_seen": {
                "2026.9.4": "2026-09-30T12:00:00+00:00",
                "2026.10.2": "2026-10-10T12:00:00+00:00",
            }
        },
    }
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert manager.async_get_first_seen("2026.10.2") == dt_util.parse_datetime(
        "2026-10-10T12:00:00+00:00"
    )
    assert manager.async_get_first_seen("2026.9.4") is None


@pytest.mark.parametrize("missing", ["version", "version_latest"])
async def test_first_seen_unknown_version(
    hass: HomeAssistant, homeassistant_info: AsyncMock, missing: str
) -> None:
    """Test nothing is recorded while Supervisor does not know a version."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, **{missing: None}
    )
    await _setup_hassio(hass)

    assert hass.data[DATA_AUTO_UPDATE].async_get_first_seen("2026.10.2") is None


async def test_available(hass: HomeAssistant) -> None:
    """Test the feature is available on Home Assistant OS on the stable channel."""
    await _setup_hassio(hass)

    assert hass.data[DATA_AUTO_UPDATE].unavailable_reason is None


async def test_unavailable_not_home_assistant_os(
    hass: HomeAssistant, supervisor_root_info: AsyncMock
) -> None:
    """Test the feature is unavailable when not on Home Assistant OS."""
    supervisor_root_info.return_value = replace(
        supervisor_root_info.return_value, hassos=None
    )
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert (
        manager.unavailable_reason is AutoUpdateUnavailableReason.NOT_HOME_ASSISTANT_OS
    )
    assert manager.async_get_first_seen("2026.10.2") is None


@pytest.mark.parametrize("channel", [UpdateChannel.BETA, UpdateChannel.DEV])
async def test_unavailable_not_stable_channel(
    hass: HomeAssistant, supervisor_info: AsyncMock, channel: UpdateChannel
) -> None:
    """Test the feature is unavailable on the beta and dev channels."""
    supervisor_info.return_value = replace(
        supervisor_info.return_value, channel=channel
    )
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert manager.unavailable_reason is AutoUpdateUnavailableReason.NOT_STABLE_CHANNEL
    assert manager.async_get_first_seen("2026.10.2") is None


CORE_UPDATE_ENTITY_ID = "update.home_assistant_core_update"


async def _call_update_service(hass: HomeAssistant, service: str) -> None:
    """Call an update action on the Home Assistant Core update entity."""
    await hass.services.async_call(
        "update", service, {"entity_id": CORE_UPDATE_ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()


async def test_skipped_version_outlives_newer_release(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    homeassistant_info: AsyncMock,
) -> None:
    """Test a skipped version stays skipped once a newer version is offered."""
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    await _call_update_service(hass, "skip")

    assert manager.async_is_skipped("2026.10.2")
    assert hass_storage[STORAGE_KEY]["data"]["skipped"] == ["2026.10.2"]

    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.3"
    )
    await _refresh_main_coordinator(hass, freezer)

    # The update entity offers the newer version again, as designed
    state = hass.states.get(CORE_UPDATE_ENTITY_ID)
    assert state.state == "on"
    assert state.attributes["skipped_version"] is None
    assert manager.async_is_skipped("2026.10.2")
    assert not manager.async_is_skipped("2026.10.3")


async def test_clearing_skipped_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test clearing the skip on the update entity allows the version again."""
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    await _call_update_service(hass, "skip")
    await _call_update_service(hass, "clear_skipped")

    assert not manager.async_is_skipped("2026.10.2")
    assert hass_storage[STORAGE_KEY]["data"]["skipped"] == []


async def test_skipped_version_survives_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test stored skipped versions are kept and older majors are dropped."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "key": STORAGE_KEY,
        "data": {"first_seen": {}, "skipped": ["2026.9.3", "2026.10.2"]},
    }
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert manager.async_is_skipped("2026.10.2")
    assert not manager.async_is_skipped("2026.9.3")


async def test_store_migration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test a store without skipped versions is migrated."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"first_seen": {"2026.10.2": "2026-10-10T12:00:00+00:00"}},
    }
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]

    assert not manager.async_is_skipped("2026.10.2")
    assert manager.async_get_first_seen("2026.10.2") == dt_util.parse_datetime(
        "2026-10-10T12:00:00+00:00"
    )


async def test_skipped_version_kept_while_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    homeassistant_info: AsyncMock,
) -> None:
    """Test the update entity going unavailable does not clear the skip."""
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]
    await _call_update_service(hass, "skip")

    homeassistant_info.side_effect = SupervisorError("Boom")
    await _refresh_main_coordinator(hass, freezer)

    assert hass.states.get(CORE_UPDATE_ENTITY_ID).state == "unavailable"
    assert manager.async_is_skipped("2026.10.2")

    homeassistant_info.side_effect = None
    await _refresh_main_coordinator(hass, freezer)

    assert hass.states.get(CORE_UPDATE_ENTITY_ID).state == "off"
    assert manager.async_is_skipped("2026.10.2")


async def test_skipped_version_after_rename(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test skipping still reaches the skip list after renaming the entity."""
    await _setup_hassio(hass)
    manager = hass.data[DATA_AUTO_UPDATE]
    entity_registry.async_update_entity(
        CORE_UPDATE_ENTITY_ID, new_entity_id="update.renamed_core"
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "skip", {"entity_id": "update.renamed_core"}, blocking=True
    )
    await hass.async_block_till_done()

    assert manager.async_is_skipped("2026.10.2")

    await hass.services.async_call(
        "update", "clear_skipped", {"entity_id": "update.renamed_core"}, blocking=True
    )
    await hass.async_block_till_done()

    assert not manager.async_is_skipped("2026.10.2")
