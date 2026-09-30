"""Tests Starlink integration init/unload."""

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .patchers import (
    HISTORY_STATS_SUCCESS_PATCHER,
    LOCATION_DATA_SUCCESS_PATCHER,
    LOCATION_DATA_UNAVAILABLE_PATCHER,
    LOCATION_DATA_UNIMPLEMENTED_PATCHER,
    SLEEP_DATA_SUCCESS_PATCHER,
    SLEEP_DATA_UNAVAILABLE_PATCHER,
    SLEEP_DATA_UNIMPLEMENTED_PATCHER,
    STATUS_DATA_FIXTURE,
    STATUS_DATA_SUCCESS_PATCHER,
    STATUS_DATA_TARGET,
    STATUS_DATA_UNAVAILABLE_PATCHER,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


def _entity_state(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity's state, asserting it's registered."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


async def test_successful_entry(hass: HomeAssistant) -> None:
    """Test configuring Starlink."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data
        assert entry.runtime_data.data
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "location_patcher",
    [LOCATION_DATA_SUCCESS_PATCHER, LOCATION_DATA_UNIMPLEMENTED_PATCHER],
    ids=["location_available", "location_unimplemented"],
)
@pytest.mark.parametrize(
    "sleep_patcher",
    [SLEEP_DATA_SUCCESS_PATCHER, SLEEP_DATA_UNIMPLEMENTED_PATCHER],
    ids=["sleep_available", "sleep_unimplemented"],
)
async def test_setup_with_unimplemented_location_or_sleep(
    hass: HomeAssistant,
    location_patcher: patch,
    sleep_patcher: patch,
) -> None:
    """Test that setup still succeeds when the dish reports GetLocation/DishGetConfig as Unimplemented.

    Some Starlink plans (e.g. non-Priority) return Unimplemented for these two
    calls. The integration should still load and simply omit that data,
    rather than failing setup entirely.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        location_patcher,
        sleep_patcher,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data
        assert entry.runtime_data.data


async def test_sleep_entities_not_created_when_sleep_unimplemented(
    hass: HomeAssistant,
) -> None:
    """Test sleep-related entities aren't created at all when unsupported.

    Rather than creating a switch/time entities that would forever report
    "unavailable" (or worse, a fabricated but non-functional "off"), don't
    add them in the first place when the first refresh determines this
    dish/plan doesn't support sleep config.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_UNIMPLEMENTED_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.data.sleep is None
        assert hass.states.get("switch.starlink_sleep_schedule") is None
        assert hass.states.get("time.starlink_sleep_start") is None
        assert hass.states.get("time.starlink_sleep_end") is None
        # A switch unrelated to sleep config must stay unaffected.
        assert _entity_state(hass, "switch.starlink_stowed") == "off"


@pytest.mark.parametrize(
    ("location_patcher", "expect_registered"),
    [
        pytest.param(LOCATION_DATA_SUCCESS_PATCHER, True, id="location_available"),
        pytest.param(
            LOCATION_DATA_UNIMPLEMENTED_PATCHER, False, id="location_unimplemented"
        ),
    ],
)
async def test_device_tracker_only_created_when_location_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    location_patcher: patch,
    expect_registered: bool,
) -> None:
    """Test the device tracker is only registered when location is supported.

    device_location is disabled by default, so checking hass.states wouldn't
    distinguish "not created" from "created but disabled" - check the entity
    registry directly instead.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        location_patcher,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        entity_id = entity_registry.async_get_entity_id(
            "device_tracker",
            DOMAIN,
            f"{entry.runtime_data.data.status['id']}_device_location",
        )
        assert (entity_id is not None) is expect_registered


async def test_device_tracker_unavailable_when_location_becomes_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tracker goes unavailable if a later poll finds location unsupported.

    Regression guard: location can go from supported to None mid-session (the
    entity was already registered on a prior successful poll), and latitude_fn
    etc. returning None must not be mistaken for a real "unknown location" -
    the entity should report unavailable, not a stale/blank location.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = entity_registry.async_get_entity_id(
            "device_tracker",
            DOMAIN,
            f"{entry.runtime_data.data.status['id']}_device_location",
        )
        assert entity_id is not None
        entity_registry.async_update_entity(entity_id, disabled_by=None)
        await hass.async_block_till_done()

        # Enabling a previously-disabled entity schedules its own debounced
        # reload (RELOAD_AFTER_UPDATE_DELAY); let it fire instead of racing
        # it with a manual reload, which would leave the timer lingering.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

        assert _entity_state(hass, entity_id) != "unavailable"

        with LOCATION_DATA_UNIMPLEMENTED_PATCHER:
            await entry.runtime_data.async_refresh()

        assert entry.runtime_data.last_update_success is True
        assert entry.runtime_data.data.location is None
        assert _entity_state(hass, entity_id) == "unavailable"


async def test_sleep_switch_reports_real_off_when_supported(
    hass: HomeAssistant,
) -> None:
    """Test the sleep switch reports a real, interactable 'off' when supported.

    Guards against a fix for the above accidentally treating a genuine,
    supported "schedule disabled" as unavailable too.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("switch.starlink_sleep_schedule")
        assert state is not None
        assert state.state in ("on", "off")


async def test_switches_unavailable_when_coordinator_refresh_fails(
    hass: HomeAssistant,
) -> None:
    """Test switches go unavailable when the coordinator itself fails to refresh.

    Regression guard: the per-switch available_fn must not bypass
    CoordinatorEntity's own availability (coordinator.last_update_success).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert _entity_state(hass, "switch.starlink_stowed") == "off"
        assert _entity_state(hass, "switch.starlink_sleep_schedule") in ("on", "off")

        with STATUS_DATA_UNAVAILABLE_PATCHER:
            await entry.runtime_data.async_refresh()

        assert entry.runtime_data.last_update_success is False
        assert _entity_state(hass, "switch.starlink_stowed") == "unavailable"
        assert _entity_state(hass, "switch.starlink_sleep_schedule") == "unavailable"


@pytest.mark.parametrize(
    ("location_patcher", "sleep_patcher"),
    [
        pytest.param(
            LOCATION_DATA_UNAVAILABLE_PATCHER,
            SLEEP_DATA_SUCCESS_PATCHER,
            id="location_unavailable",
        ),
        pytest.param(
            LOCATION_DATA_SUCCESS_PATCHER,
            SLEEP_DATA_UNAVAILABLE_PATCHER,
            id="sleep_unavailable",
        ),
        pytest.param(
            LOCATION_DATA_UNAVAILABLE_PATCHER,
            SLEEP_DATA_UNAVAILABLE_PATCHER,
            id="both_unavailable",
        ),
    ],
)
async def test_setup_retries_on_other_grpc_errors(
    hass: HomeAssistant,
    location_patcher: patch,
    sleep_patcher: patch,
) -> None:
    """Test that non-Unimplemented gRPC errors still fail setup as before.

    Only Unimplemented should be swallowed. A real communication failure
    (e.g. Unavailable) must still surface as a failed/retried setup instead
    of being silently treated as "no data".
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        location_patcher,
        sleep_patcher,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Starlink."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_restore_cache_with_accumulation(hass: HomeAssistant) -> None:
    """Test Starlink accumulation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )
    entity_id = "sensor.starlink_energy"

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    entity_id,
                    "",
                ),
                {
                    "native_value": 1,
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data
        assert entry.runtime_data.data

        assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

        await entry.runtime_data.async_refresh()

        assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

        with patch.object(entry.runtime_data, "always_update", return_value=True):
            await entry.runtime_data.async_refresh()

        assert hass.states.get(entity_id).state == str(1 + 0.01572462736977)


async def test_last_restart_state(hass: HomeAssistant) -> None:
    """Test Starlink last restart state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )
    entity_id = "sensor.starlink_last_restart"
    utc_now = datetime.fromisoformat("2025-10-22T13:31:29+00:00")

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        with freeze_time(utc_now):
            entry.add_to_hass(hass)

            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        with patch.object(entry.runtime_data, "always_update", return_value=True):
            status_data = deepcopy(STATUS_DATA_FIXTURE)
            status_data[0]["uptime"] = 804144

            with (
                freeze_time(utc_now + timedelta(seconds=5)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

            status_data[0]["uptime"] = 804134

            with (
                freeze_time(utc_now + timedelta(seconds=10)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

            status_data[0]["uptime"] = 100

            with (
                freeze_time(utc_now + timedelta(seconds=15)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-22T13:30:04+00:00"
