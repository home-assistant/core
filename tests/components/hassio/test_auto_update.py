"""Test automatic Home Assistant updates."""

import asyncio
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import HomeAssistantUpdateOptions, Job, UpdateChannel
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.backup import (
    CreateBackupEvent,
    CreateBackupStage,
    CreateBackupState,
    IdleEvent,
)
from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.auto_update import (
    AUTO_UPDATE_OPTIONS_SCHEMA,
    CHECK_INTERVAL,
    AutoUpdateSettings,
    AutoUpdateUnavailableReason,
)
from homeassistant.components.hassio.const import (
    DATA_AUTO_UPDATE,
    EVENT_SUPERVISOR_EVENT,
    HASSIO_MAIN_UPDATE_INTERVAL,
    MAIN_COORDINATOR,
)
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}
STORAGE_KEY = "hassio.auto_update"


@pytest.fixture(autouse=True)
def mock_window_offset() -> Generator[None]:
    """Update at the start of the time window, unless a test says otherwise."""
    with patch(
        "homeassistant.components.hassio.auto_update.random.random", return_value=0.0
    ):
        yield


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
        pytest.param(
            {
                "core_auto_update_window_start": "03:00",
                "core_auto_update_window_end": "03:15",
            },
            id="too_short",
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
        "withdrawn": [],
        "window_offset": 0.0,
        "attempted_window": None,
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


ENABLED = {"core_auto_update": True}


def _local(day: int, hour: int, minute: int = 0) -> datetime:
    """Return a local time in October 2026; the 19th is a Monday."""
    return datetime(2026, 10, day, hour, minute, tzinfo=dt_util.get_default_time_zone())


async def _setup_scheduled(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    now: datetime,
    *,
    first_seen: dict[str, datetime],
    options: dict[str, Any] | None = None,
    skipped: list[str] | None = None,
    withdrawn: list[str] | None = None,
    window_offset: float = 0.0,
) -> None:
    """Set up hassio at a given time with known first-seen times.

    Home Assistant is already running in tests, so the first check runs
    during setup.
    """
    freezer.move_to(now)
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 3,
        "key": STORAGE_KEY,
        "data": {
            "first_seen": {
                version: seen.isoformat() for version, seen in first_seen.items()
            },
            "skipped": skipped or [],
            "withdrawn": withdrawn or [],
            "window_offset": window_offset,
            "attempted_window": None,
        },
    }
    await _setup_hassio(hass, ENABLED if options is None else options)


def _installed(supervisor_client: AsyncMock) -> list[str | None]:
    """Return the versions Supervisor was asked to install."""
    return [
        call.args[0].version
        for call in supervisor_client.homeassistant.update.call_args_list
    ]


async def test_installs_patch_in_window(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test a patch that waited long enough installs inside the window."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    supervisor_client.homeassistant.update.assert_called_once_with(
        HomeAssistantUpdateOptions(version="2026.10.2", backup=False)
    )


@pytest.mark.parametrize(
    ("now", "options"),
    [
        pytest.param(_local(22, 3, 30), {}, id="not_chosen"),
        pytest.param(_local(22, 3, 30), {"core_auto_update": False}, id="disabled"),
        pytest.param(_local(21, 3, 30), ENABLED, id="wait_not_passed"),
        pytest.param(_local(22, 2, 59), ENABLED, id="before_window"),
        pytest.param(_local(22, 5, 0), ENABLED, id="after_window"),
        pytest.param(
            _local(22, 3, 30),
            {**ENABLED, "core_auto_update_weekdays": ["mon"]},
            id="weekday_not_allowed",
        ),
    ],
)
async def test_no_install(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    now: datetime,
    options: dict[str, Any],
) -> None:
    """Test nothing installs when disabled, too early or outside the window."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        now,
        first_seen={"2026.10.2": _local(19, 2)},
        options=options,
    )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_window_crossing_midnight(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test a window that crosses midnight belongs to the day it starts."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 0, 30),
        first_seen={"2026.10.2": _local(18, 2)},
        options={
            **ENABLED,
            "core_auto_update_window_start": "23:00:00",
            "core_auto_update_window_end": "01:00:00",
            "core_auto_update_weekdays": ["wed"],
        },
    )

    assert _installed(supervisor_client) == ["2026.10.2"]


@pytest.mark.parametrize(
    ("first_seen", "version_latest", "skipped", "expected"),
    [
        pytest.param(
            {"2026.10.2": _local(19, 2), "2026.10.3": _local(21, 2)},
            "2026.10.3",
            [],
            [],
            id="newer_patch_still_waits",
        ),
        pytest.param(
            {"2026.10.2": _local(18, 2), "2026.10.3": _local(19, 2)},
            "2026.10.3",
            [],
            ["2026.10.3"],
            id="newest_of_both",
        ),
        pytest.param(
            {"2026.10.2": _local(19, 2), "2026.11.0": _local(19, 2)},
            "2026.11.0",
            [],
            ["2026.10.2"],
            id="major_never",
        ),
        pytest.param(
            {"2026.10.2": _local(19, 2), "2026.10.3": _local(19, 2)},
            "2026.10.2",
            [],
            ["2026.10.2"],
            id="pulled_release",
        ),
        pytest.param(
            {"2026.10.2": _local(19, 2)},
            "2026.10.1",
            [],
            [],
            id="everything_pulled",
        ),
        pytest.param(
            {"2026.10.2": _local(19, 2)},
            "2026.10.2",
            ["2026.10.2"],
            [],
            id="skipped",
        ),
        pytest.param(
            {"2026.10.2": _local(19, 2), "2026.10.3": _local(19, 2)},
            "2026.10.3",
            ["2026.10.3"],
            [],
            id="skipped_newest_waits_for_next",
        ),
    ],
)
async def test_install_candidate(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
    first_seen: dict[str, datetime],
    version_latest: str,
    skipped: list[str],
    expected: list[str],
) -> None:
    """Test which version is picked for an automatic update."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest=version_latest
    )
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen=first_seen,
        skipped=skipped,
    )

    assert _installed(supervisor_client) == expected


async def test_window_offset(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test each installation updates from its own point in the window."""
    # Halfway the 03:00 to 05:00 window, less one check: 03:57:30
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 55),
        first_seen={"2026.10.2": _local(19, 2)},
        window_offset=0.5,
    )

    supervisor_client.homeassistant.update.assert_not_called()

    freezer.tick(CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _installed(supervisor_client) == ["2026.10.2"]


def _core_update_job(done: bool) -> Job:
    """Return a Supervisor job for updating Home Assistant Core."""
    return Job(
        name="home_assistant_core_update",
        reference=None,
        uuid=uuid4(),
        progress=0,
        stage=None,
        done=done,
        errors=[],
        created=dt_util.utcnow(),
        child_jobs=[],
        extra=None,
    )


async def test_no_install_while_busy(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    jobs_info: AsyncMock,
) -> None:
    """Test nothing installs while a backup runs."""
    jobs_info.return_value = replace(
        jobs_info.return_value,
        jobs=[
            Job(
                name="backup_manager_partial_backup",
                reference=None,
                uuid=uuid4(),
                progress=0,
                stage=None,
                done=False,
                errors=[],
                created=dt_util.utcnow(),
                child_jobs=[],
                extra=None,
            )
        ],
    )
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_no_install_in_safe_mode(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs in safe mode."""
    hass.config.safe_mode = True
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_backup_before_update(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test a backup is made first when the update settings ask for it."""
    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update"
    ) as mock_backup:
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )

    mock_backup.assert_called_once_with(hass)
    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_one_attempt_per_window(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed update is not retried in the same window."""
    supervisor_client.homeassistant.update.side_effect = SupervisorError("Boom")
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    assert "Automatic update to Home Assistant 2026.10.2 failed" in caplog.text

    freezer.tick(CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _installed(supervisor_client) == ["2026.10.2"]

    freezer.move_to(_local(23, 3, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _installed(supervisor_client) == ["2026.10.2", "2026.10.2"]


async def test_no_install_while_backup_uploads(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs while Core still uploads a backup to its agents."""
    uploading = CreateBackupEvent(
        reason=None,
        stage=CreateBackupStage.UPLOAD_TO_AGENTS,
        state=CreateBackupState.IN_PROGRESS,
    )
    with patch(
        "homeassistant.components.backup.async_get_manager",
        return_value=Mock(last_event=uploading),
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
        )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_no_install_on_stale_data(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test nothing installs while Supervisor data cannot be refreshed."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 2, 50),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    homeassistant_info.side_effect = SupervisorError("Boom")
    freezer.tick(CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.tick(CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert dt_util.now() >= _local(22, 3)
    supervisor_client.homeassistant.update.assert_not_called()


async def test_no_retry_after_reload(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test a failed attempt is remembered when the integration reloads."""
    supervisor_client.homeassistant.update.side_effect = SupervisorError("Boom")
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    assert hass_storage[STORAGE_KEY]["data"]["attempted_window"] == (
        dt_util.as_utc(_local(22, 3)).isoformat()
    )

    freezer.tick(CHECK_INTERVAL)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_no_retry_after_reload_when_clocks_go_back(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test the attempted window matches in the hour that happens twice."""
    await hass.config.async_set_time_zone("Europe/Helsinki")
    supervisor_client.homeassistant.update.side_effect = SupervisorError("Boom")
    # 03:30 local on 25 October 2026 happens twice; this is the first time
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        first_seen={"2026.10.2": datetime(2026, 10, 19, tzinfo=UTC)},
    )

    freezer.tick(CHECK_INTERVAL)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_unload_during_backup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test unloading while the backup runs stops the update."""
    backup_done = asyncio.Event()

    async def slow_backup(hass: HomeAssistant) -> None:
        await backup_done.wait()

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=slow_backup,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        backup_done.set()
        await hass.async_block_till_done()

    supervisor_client.homeassistant.update.assert_not_called()


async def test_backup_may_run_past_window(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test the window bounds when the update starts, not when it ends."""

    async def slow_backup(hass: HomeAssistant) -> None:
        freezer.move_to(_local(22, 5, 10))

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=slow_backup,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 4, 59),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )

    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_skipped_during_backup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs when the version was skipped while backing up."""
    backup_done = asyncio.Event()

    async def slow_backup(hass: HomeAssistant) -> None:
        await backup_done.wait()

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=slow_backup,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )
        await _call_update_service(hass, "skip")
        backup_done.set()
        await hass.async_block_till_done()

    supervisor_client.homeassistant.update.assert_not_called()


async def test_data_stale_after_backup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs when Supervisor data went stale during the backup."""

    async def backup_while_supervisor_fails(hass: HomeAssistant) -> None:
        hass.data[MAIN_COORDINATOR].async_set_update_error(UpdateFailed("Boom"))

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=backup_while_supervisor_fails,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_other_update_during_backup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs when someone else started an update meanwhile."""
    backup_done = asyncio.Event()

    async def slow_backup(hass: HomeAssistant) -> None:
        await backup_done.wait()

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=slow_backup,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )
        async_dispatcher_send(
            hass,
            EVENT_SUPERVISOR_EVENT,
            {"event": "job", "data": _core_update_job(done=False).to_dict()},
        )
        backup_done.set()
        await hass.async_block_till_done()

    supervisor_client.homeassistant.update.assert_not_called()


async def test_own_backup_job_after_backup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    jobs_info: AsyncMock,
) -> None:
    """Test our own backup still showing as running does not stop the update."""

    async def backup_still_listed(hass: HomeAssistant) -> None:
        async_dispatcher_send(
            hass,
            EVENT_SUPERVISOR_EVENT,
            {
                "event": "job",
                "data": {
                    **_core_update_job(done=False).to_dict(),
                    "name": "backup_manager_partial_backup",
                },
            },
        )

    with patch(
        "homeassistant.components.hassio.backup.backup_core_before_update",
        side_effect=backup_still_listed,
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )

    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_withdrawn_then_replaced(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test a withdrawn release is not installed once a replacement is offered."""
    # 2026.10.2 waited long enough, but Supervisor withdrew it again
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.1"
    )
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.3"
    )
    await _refresh_main_coordinator(hass, freezer)
    # A check that sees 2026.10.3 offered
    freezer.tick(CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    supervisor_client.homeassistant.update.assert_not_called()

    freezer.move_to(_local(26, 3, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _installed(supervisor_client) == ["2026.10.3"]


async def test_turned_off_while_saving(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test turning automatic updates off during the last save stops the update."""
    save = Store.async_save

    async def save_and_turn_off(store: Store, data: Any) -> None:
        await save(store, data)
        if store.key == STORAGE_KEY and data["attempted_window"] is not None:
            entry = hass.config_entries.async_entries(DOMAIN)[0]
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, "core_auto_update": False}
            )

    with patch.object(Store, "async_save", save_and_turn_off):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
        )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_withdrawn_then_replacement_skipped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test skipping the replacement does not bring a withdrawn release back."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.1"
    )
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )

    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.10.3"
    )
    await _refresh_main_coordinator(hass, freezer)
    await _call_update_service(hass, "skip")

    assert hass.data[DATA_AUTO_UPDATE].async_is_skipped("2026.10.3")

    freezer.move_to(_local(26, 3, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    supervisor_client.homeassistant.update.assert_not_called()


async def _offer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    homeassistant_info: AsyncMock,
    version: str,
) -> None:
    """Let Supervisor offer a version and the coordinator pick it up."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest=version
    )
    await _refresh_main_coordinator(hass, freezer)


async def test_withdrawn_then_new_major(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test a pulled patch stays out once the next major is offered."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 2, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )
    await _offer(hass, freezer, homeassistant_info, "2026.10.1")
    await _offer(hass, freezer, homeassistant_info, "2026.11.0")

    assert hass_storage[STORAGE_KEY]["data"]["withdrawn"] == ["2026.10.2"]

    freezer.move_to(_local(22, 3, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    supervisor_client.homeassistant.update.assert_not_called()


async def test_withdrawn_offered_again(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test a pulled patch is eligible again once Supervisor offers it again."""
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 2, 30),
        first_seen={"2026.10.2": _local(19, 2)},
    )
    await _offer(hass, freezer, homeassistant_info, "2026.10.1")
    await _offer(hass, freezer, homeassistant_info, "2026.10.2")

    assert hass_storage[STORAGE_KEY]["data"]["withdrawn"] == []

    freezer.move_to(_local(22, 3, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _installed(supervisor_client) == ["2026.10.2"]


async def test_withdrawn_survives_restart(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
    homeassistant_info: AsyncMock,
) -> None:
    """Test a stored withdrawal keeps the patch out after a restart."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, version_latest="2026.11.0"
    )
    await _setup_scheduled(
        hass,
        hass_storage,
        freezer,
        _local(22, 3, 30),
        first_seen={"2026.10.2": _local(19, 2)},
        withdrawn=["2026.10.2"],
    )

    supervisor_client.homeassistant.update.assert_not_called()


async def test_other_backup_started_after_ours(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    supervisor_client: AsyncMock,
) -> None:
    """Test nothing installs when another backup starts right after ours."""
    uploading = CreateBackupEvent(
        reason=None,
        stage=CreateBackupStage.UPLOAD_TO_AGENTS,
        state=CreateBackupState.IN_PROGRESS,
    )

    backup_manager = Mock(last_event=IdleEvent())

    async def backup_then_another(hass: HomeAssistant) -> None:
        backup_manager.last_event = uploading

    with (
        patch(
            "homeassistant.components.backup.async_get_manager",
            return_value=backup_manager,
        ),
        patch(
            "homeassistant.components.hassio.backup.backup_core_before_update",
            side_effect=backup_then_another,
        ),
    ):
        await _setup_scheduled(
            hass,
            hass_storage,
            freezer,
            _local(22, 3, 30),
            first_seen={"2026.10.2": _local(19, 2)},
            options={**ENABLED, "core_backup_before_update": True},
        )

    supervisor_client.homeassistant.update.assert_not_called()
