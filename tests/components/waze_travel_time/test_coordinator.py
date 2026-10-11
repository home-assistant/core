"""Test automatic Waze polling intervals."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywaze.route_calculator import WRCError

from homeassistant.components.waze_travel_time.config_flow import WazeConfigFlow
from homeassistant.components.waze_travel_time.const import DEFAULT_OPTIONS, DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def no_api_delay() -> Generator[None]:
    """Avoid real delays between mocked requests."""
    with patch(
        "homeassistant.components.waze_travel_time.coordinator.SECONDS_BETWEEN_API_CALLS",
        0,
    ):
        yield


@pytest.fixture
def route_entries() -> list[MockConfigEntry]:
    """Create independently configured routes."""
    return [
        MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG,
            options=DEFAULT_OPTIONS,
            version=WazeConfigFlow.VERSION,
            minor_version=WazeConfigFlow.MINOR_VERSION,
        )
        for _ in range(91)
    ]


@pytest.mark.parametrize(
    ("route_count", "minutes"),
    [
        pytest.param(3, 5, id="minimum_interval"),
        pytest.param(4, 6, id="above_minimum_interval"),
        pytest.param(10, 14, id="multiple_rounds"),
        pytest.param(90, 121, id="exactly_one_round"),
        pytest.param(91, 122, id="more_than_reserved_budget"),
    ],
)
async def test_polling_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_update: AsyncMock,
    route_entries: list[MockConfigEntry],
    route_count: int,
    minutes: int,
) -> None:
    """All loaded routes share the interval, including concurrent startup."""
    entries = route_entries[:route_count]
    for entry in entries:
        entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert mock_update.call_count == route_count
    assert all(
        entry.runtime_data.update_interval == timedelta(minutes=minutes)
        for entry in entries
    )

    mock_update.reset_mock()
    freezer.tick(timedelta(minutes=minutes - 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_update.assert_not_called()

    freezer.tick(timedelta(minutes=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_update.call_count == route_count


@pytest.mark.parametrize(
    ("route_count", "expected_max_requests"),
    [
        pytest.param(17, 85, id="seventeen"),
        pytest.param(45, 90, id="exactly_two_rounds"),
        pytest.param(90, 90, id="exactly_one_round"),
    ],
)
async def test_polling_round_budget(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_update: AsyncMock,
    route_entries: list[MockConfigEntry],
    route_count: int,
    expected_max_requests: int,
) -> None:
    """Repeated polling rounds never exceed the budget within a two-hour window."""
    for entry in route_entries[:route_count]:
        entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_update.call_count == route_count

    # Include startup requests, then observe every minute for two quota windows.
    request_minutes = [0] * route_count
    max_requests = route_count
    previous_requests = route_count
    for minute in range(1, 241):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        new_requests = mock_update.call_count - previous_requests
        request_minutes.extend([minute] * new_requests)
        previous_requests = mock_update.call_count

        # Count both window boundaries to catch an extra round at the reset time.
        requests_in_window = sum(
            request_minute >= minute - 120 for request_minute in request_minutes
        )
        assert requests_in_window <= 90
        max_requests = max(max_requests, requests_in_window)

    assert max_requests == expected_max_requests


async def test_entry_lifecycle(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_update: AsyncMock,
    route_entries: list[MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Adding, unloading, disabling, enabling and removing recalculate intervals."""
    # One active route uses the minimum interval.
    first, *others = route_entries[:4]
    first.add_to_hass(hass)
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    coordinator = first.runtime_data
    assert coordinator.update_interval == timedelta(minutes=5)

    # Adding routes updates the already-running coordinator as well as new ones.
    for entry in others:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert all(
        entry.runtime_data.update_interval == timedelta(minutes=6)
        for entry in route_entries[:4]
    )

    # Unloading the fourth route restores the interval for three active routes.
    last = others[-1]
    assert await hass.config_entries.async_unload(last.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=5)

    # The remaining timers must use five minutes, not their previous six minutes.
    mock_update.reset_mock()
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_update.call_count == 3

    # Loading the route again must count it exactly once.
    assert await hass.config_entries.async_setup(last.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=6)

    # Disabling and enabling the entry must remove and restore its polling cost.
    assert await hass.config_entries.async_set_disabled_by(
        last.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=5)

    assert await hass.config_entries.async_set_disabled_by(last.entry_id, None)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=6)

    # A loaded entry stops participating when its only sensor is disabled.
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, last.entry_id)
    assert entity_id is not None
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert last.state is ConfigEntryState.LOADED
    assert coordinator.update_interval == timedelta(minutes=5)

    # Enabling the sensor and reloading restores automatic polling.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(last.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=6)

    # Removing a route adjusts the interval without reloading the other entries.
    assert await hass.config_entries.async_remove(last.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=5)
    assert first.runtime_data is coordinator


@pytest.mark.usefixtures("mock_update")
@pytest.mark.parametrize(
    ("disable_polling", "disable_sensor"),
    [
        pytest.param(True, None, id="polling_disabled"),
        pytest.param(False, er.RegistryEntryDisabler.USER, id="sensor_disabled"),
    ],
)
async def test_too_many_polling_routes_issue(
    hass: HomeAssistant,
    route_entries: list[MockConfigEntry],
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    disable_polling: bool,
    disable_sensor: er.RegistryEntryDisabler | None,
) -> None:
    """Warn only above the automatic polling budget and clear on lifecycle changes."""
    # Ninety active routes fit one round; a non-polling entry must not trigger a warning.
    for entry in route_entries[:90]:
        entry.add_to_hass(hass)
    extra = route_entries[90]
    extra.add_to_hass(hass)
    hass.config_entries.async_update_entry(extra, pref_disable_polling=disable_polling)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        extra.entry_id,
        config_entry=extra,
        disabled_by=disable_sensor,
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert not issue_registry.issues

    # Enabling the ninety-first route creates one shared, actionable warning.
    hass.config_entries.async_update_entry(extra, pref_disable_polling=False)
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, extra.entry_id)
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(DOMAIN, "too_many_polling_routes")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_key == "too_many_polling_routes"
    assert issue.translation_placeholders == {"max_routes": "90"}
    assert (
        issue.learn_more_url
        == "https://www.home-assistant.io/integrations/waze_travel_time/#defining-a-custom-polling-interval"
    )
    assert len(issue_registry.issues) == 1

    # Reloading must not duplicate the warning; unloading must clear it.
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1
    assert await hass.config_entries.async_unload(extra.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.issues
    assert await hass.config_entries.async_setup(extra.entry_id)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1

    # Disabling automatic polling is one of the actions recommended by the Repair.
    hass.config_entries.async_update_entry(extra, pref_disable_polling=True)
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.issues
    hass.config_entries.async_update_entry(extra, pref_disable_polling=False)
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1

    # Disabling the only sensor stops polling even though its entry stays loaded.
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert extra.state is ConfigEntryState.LOADED
    assert not issue_registry.issues
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1

    # Disabling or removing an entry also resolves the warning.
    assert await hass.config_entries.async_set_disabled_by(
        extra.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert not issue_registry.issues
    assert await hass.config_entries.async_set_disabled_by(extra.entry_id, None)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1
    assert await hass.config_entries.async_remove(extra.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.issues


@pytest.mark.parametrize(
    ("disable_polling", "disable_sensor"),
    [
        pytest.param(True, None, id="polling_disabled"),
        pytest.param(False, er.RegistryEntryDisabler.USER, id="sensor_disabled"),
    ],
)
async def test_non_polling_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_update: AsyncMock,
    route_entries: list[MockConfigEntry],
    entity_registry: er.EntityRegistry,
    disable_polling: bool,
    disable_sensor: er.RegistryEntryDisabler | None,
) -> None:
    """Routes with polling disabled or no enabled entities do not share the budget."""
    for entry in route_entries[:3]:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    extra = route_entries[3]
    extra.add_to_hass(hass)
    hass.config_entries.async_update_entry(extra, pref_disable_polling=disable_polling)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        extra.entry_id,
        config_entry=extra,
        disabled_by=disable_sensor,
    )
    assert await hass.config_entries.async_setup(extra.entry_id)
    await hass.async_block_till_done()
    assert extra.state is ConfigEntryState.LOADED
    assert mock_update.call_count == 4  # Startup still fetches the route.
    assert all(
        entry.runtime_data.update_interval == timedelta(minutes=5)
        for entry in route_entries[:3]
    )

    mock_update.reset_mock()
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_update.call_count == 3

    # Enabling the route uses the normal entry reload lifecycle.
    hass.config_entries.async_update_entry(extra, pref_disable_polling=False)
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, extra.entry_id)
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert all(
        entry.runtime_data.update_interval == timedelta(minutes=6)
        for entry in route_entries[:4]
    )


async def test_setup_retry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_update: AsyncMock,
    route_entries: list[MockConfigEntry],
) -> None:
    """Failed setup and retries never leave stale or duplicate polling routes."""
    # Three active routes provide the five-minute baseline.
    for entry in route_entries[:3]:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = route_entries[0].runtime_data
    extra = route_entries[3]
    extra.add_to_hass(hass)

    # Failed setup must not add the fourth route to the polling count.
    mock_update.side_effect = WRCError("Unavailable")
    assert not await hass.config_entries.async_setup(extra.entry_id)
    await hass.async_block_till_done()
    assert extra.state is ConfigEntryState.SETUP_RETRY
    assert coordinator.update_interval == timedelta(minutes=5)

    # Advance past the first retry delay, including its random offset.
    mock_update.reset_mock()
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_update.assert_called_once()
    assert extra.state is ConfigEntryState.SETUP_RETRY
    assert coordinator.update_interval == timedelta(minutes=5)

    # The next automatic retry succeeds and must count the fourth route once.
    mock_update.side_effect = None
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert extra.state is ConfigEntryState.LOADED
    assert coordinator.update_interval == timedelta(minutes=6)

    # Reloading must replace the registration, not add a duplicate.
    assert await hass.config_entries.async_reload(extra.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=6)

    # Unloading must remove the route without leaving a stale registration.
    assert await hass.config_entries.async_unload(extra.entry_id)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(minutes=5)
