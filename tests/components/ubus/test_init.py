"""Tests for the OpenWrt (ubus) integration setup."""

from datetime import timedelta
import logging
import threading
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import DOMAIN, SUBENTRY_TYPE_ROUTER
from homeassistant.components.ubus.coordinator import REQUEST_TIMEOUT
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    MAC_LAPTOP,
    MAC_PHONE,
    MOCK_CONFIG,
    MOCK_HOST,
    MOCK_HOST_B,
    MOCK_HOST_C,
    MOCK_HOST_CONFIG_B,
    MOCK_HOST_CONFIG_C,
    router_subentry_data,
)


async def test_setup_creates_single_coordinator(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test setup creates a single coordinator polling every router."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    assert two_router_hub.state is ConfigEntryState.LOADED
    assert ubus[MOCK_HOST].get_hostapd_clients.call_count == 1
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1


async def test_setup_entry_without_subentries(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test a hub without routers sets up without polling any router."""
    _mock, ubus = mock_ubus_by_host
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=HUB_TITLE)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert ubus[MOCK_HOST].get_hostapd_clients.call_count == 0
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 0


@pytest.mark.parametrize(
    ("method", "behavior", "dhcp_software"),
    [
        pytest.param(
            "connect", {"side_effect": TypeError}, "dnsmasq", id="unreachable"
        ),
        pytest.param(
            "connect", {"side_effect": PermissionError}, "dnsmasq", id="access_denied"
        ),
        pytest.param(
            "connect",
            {"side_effect": None, "return_value": None},
            "dnsmasq",
            id="no_session",
        ),
        pytest.param(
            "get_hostapd_clients",
            {"side_effect": PermissionError},
            "dnsmasq",
            id="session_stays_denied",
        ),
        pytest.param(
            "get_hostapd", {"return_value": {}}, "dnsmasq", id="no_hostapd_data"
        ),
        pytest.param(
            "get_hostapd_clients",
            {"side_effect": ConnectionError},
            "dnsmasq",
            id="client_query_error",
        ),
        pytest.param(
            "file_read",
            {"side_effect": ConnectionError},
            "dnsmasq",
            id="dnsmasq_lease_error",
        ),
        pytest.param(
            "get_dhcp_method",
            {"side_effect": ConnectionError},
            "odhcpd",
            id="odhcpd_lease_error",
        ),
    ],
)
async def test_first_refresh_failure_does_not_fail_setup(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    method: str,
    behavior: dict[str, Any],
) -> None:
    """Test an unreadable router is reported unreachable without failing setup."""
    getattr(mock_ubus.return_value, method).configure_mock(**behavior)

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    unreachable = [
        record for record in caplog.records if "is unreachable" in record.getMessage()
    ]
    assert len(unreachable) == 1
    assert MOCK_HOST in unreachable[0].getMessage()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param({"side_effect": None, "return_value": None}, id="no_session"),
        pytest.param(
            {"side_effect": PermissionError("login denied")},
            id="access_denied",
        ),
    ],
)
async def test_persistent_invalid_credentials_issue(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    failure: dict[str, Any],
) -> None:
    """Test failing credentials open a repair issue, closed on recovery."""
    mock_ubus.return_value.connect.configure_mock(**failure)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(mock_config_entry.subentries))
    issue = issue_registry.async_get_issue(DOMAIN, f"invalid_credentials_{subentry_id}")
    assert issue is not None
    assert issue.translation_key == "persistent_invalid_credentials"

    mock_ubus.return_value.connect.configure_mock(
        side_effect=None, return_value="session-id"
    )
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        issue_registry.async_get_issue(DOMAIN, f"invalid_credentials_{subentry_id}")
        is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subentry_added_polls_new_router(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test adding a router subentry is polled right away without a reload."""
    _mock, ubus = mock_ubus_by_host
    mock_config_entry.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType(MOCK_HOST_CONFIG_B),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=MOCK_HOST_B,
            unique_id=MOCK_HOST_B,
        ),
    )
    await hass.async_block_till_done()

    # No reload: the entry stays loaded and polls the new router.
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1

    # The new router's clients are tracked.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_partial_failure_keeps_healthy_routers_reporting(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing router does not fail the entry or hide healthy data."""
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    # Both routers report, so both clients are home.
    phone_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    laptop_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert hass.states.get(phone_id).state == STATE_HOME
    assert hass.states.get(laptop_id).state == STATE_HOME

    # Router B becomes unreachable.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The entry stays healthy: the other router still reports.
    # The phone is still home, reported by the healthy router.
    assert hass.states.get(phone_id).state == STATE_HOME
    # The laptop is only seen by the failing router, so it is unavailable.
    assert hass.states.get(laptop_id).state == STATE_UNAVAILABLE


async def test_router_unreachable_and_recovery_logged(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a router failure and its recovery are each logged once."""
    caplog.set_level(logging.INFO)
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    # With the other router carrying the tick, router A's failure does not
    # fail the refresh; only the per-router log explains it.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = ConnectionError("down")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    unreachable = [
        record for record in caplog.records if "is unreachable" in record.getMessage()
    ]
    assert len(unreachable) == 1
    assert MOCK_HOST in unreachable[0].getMessage()

    # The repeated failure stays quiet.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        len(
            [
                record
                for record in caplog.records
                if "is unreachable" in record.getMessage()
            ]
        )
        == 1
    )

    # The recovery is logged once as well.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    recovery = [
        record for record in caplog.records if "reachable again" in record.getMessage()
    ]
    assert len(recovery) == 1
    assert MOCK_HOST in recovery[0].getMessage()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_routers_failing_fails_the_tick(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test every router failing fails the tick and makes trackers unavailable."""
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert hass.states.get(entity_id).state == STATE_HOME

    # Every router becomes unreachable.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = ConnectionError
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # No healthy router can report the client.
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # The routers recover and the client is home again.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = None
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_router_reconfiguration_discards_stale_stamps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguring a router's host discards the old host's stamps.

    The subentry id survives the host change, so the old host's sightings
    must not be retained and reported as coming from the new host.
    """
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # Reconfigure the router to a different host.
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=MOCK_HOST_CONFIG_C, title=MOCK_HOST_C
    )
    await hass.async_block_till_done()

    # The new host has never seen the phone, so the old host's stamps are
    # dropped with it; the tracker is unavailable, not home on the new host.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_credentials_change_preserves_sightings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating a router's credentials keeps its sighting history.

    The router's identity is its host, so changing the password must not
    release the stamps; an away client stays grounded on the healthy router
    and reports not_home rather than unavailable.
    """
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The client disconnects, and the router keeps answering without it.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    # The router is healthy, so the absent client is known away.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME

    # Update the password on the same host.
    subentry = next(iter(mock_config_entry.subentries.values()))
    data = dict(subentry.data)
    data[CONF_PASSWORD] = "new-password"
    hass.config_entries.async_update_subentry(mock_config_entry, subentry, data=data)
    await hass.async_block_till_done()

    # The sightings survive the credentials change, as the same router
    # polls successfully; the client stays known away.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_credentials_change_during_tick_keeps_sightings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a credentials change mid-tick keeps the sighting history.

    The tick that started with the old credentials discards its in-flight
    result, but the router still polls the same host, so the stamps stay
    grounded; once polling resumes on the new configuration, the absent
    client reports not_home rather than staying unavailable.
    """
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The client disconnects, and the router keeps answering without it.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME

    poll_started = threading.Event()
    poll_release = threading.Event()

    def gated_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Hold the response so the credentials change lands mid-tick.
        poll_started.set()
        poll_release.wait()
        return {"clients": {}}

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = gated_read

    # Start the next tick and hold it in flight.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    assert await hass.async_add_executor_job(poll_started.wait, 10)

    # The password changes on the same host while the tick is in flight.
    subentry = next(iter(mock_config_entry.subentries.values()))
    data = dict(subentry.data)
    data[CONF_PASSWORD] = "new-password"
    hass.config_entries.async_update_subentry(mock_config_entry, subentry, data=data)

    poll_release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The in-flight result was for the old configuration, so the tick drops
    # it, but the stamps stand on the same host; the refresh it triggers
    # polls successfully, so the client stays known away.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_host_reconfiguration_publishes_new_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguring a router's host publishes the new source.

    The same client is seen by the new host under the same subentry id, so
    the trackers are notified of the subentry change itself rather than
    waiting for the client set to change.
    """
    _mock, ubus = mock_ubus_by_host
    clients = {"clients": {MAC_PHONE: {"authorized": True}}}
    ubus[MOCK_HOST].get_hostapd_clients.return_value = clients
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = clients
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # Reconfigure the router to a different host that sees the same client.
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=MOCK_HOST_CONFIG_B, title=MOCK_HOST_B
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


async def test_slow_router_does_not_stretch_refresh_interval(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a slow tick schedules the next tick from the tick's start.

    A router which takes twenty seconds to answer must not stretch the
    thirty second period; the next tick is due ten seconds after the
    tick completes, not thirty.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    # The first tick polled both routers.
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1

    poll_started = threading.Event()
    poll_release = threading.Event()

    def slow_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Hold the response until the test advances the clock, as a
        # router which takes twenty seconds to answer.
        poll_started.set()
        poll_release.wait()
        return {"clients": {}}

    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = slow_read

    # Start the next tick on the period, and hold it in flight while
    # the router takes twenty seconds to answer.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    assert await hass.async_add_executor_job(poll_started.wait, 10)
    freezer.tick(timedelta(seconds=20))
    poll_release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 2

    # The next tick is due ten seconds after the slow tick completed
    # (tick start plus the period), not thirty seconds after it finished.
    # Tick deadlines carry up to a second of grid jitter and
    # async_fire_time_changed covers a half second window, so the margins
    # below are wider than that in both directions.
    freezer.tick(timedelta(seconds=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 2
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 3
    freezer.tick(timedelta(seconds=13))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 3
    freezer.tick(timedelta(seconds=19))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 4


async def test_router_addition_refreshes_while_tick_in_flight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test adding a router subentry polls it right after the tick completes.

    The refresh must not be debounced away while the tick holds the refresh
    lock; the new router is polled without the debounce waiting out.
    """
    _mock, ubus = mock_ubus_by_host
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    poll_started = threading.Event()
    poll_release = threading.Event()

    def slow_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Hold the response until the test releases it.
        poll_started.set()
        poll_release.wait()
        return {"clients": {}}

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = slow_read

    # Start the next tick and hold it in flight.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    assert await hass.async_add_executor_job(poll_started.wait, 10)

    # A router is added while the tick is in flight.
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType(MOCK_HOST_CONFIG_B),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=MOCK_HOST_B,
            unique_id=MOCK_HOST_B,
        ),
    )
    poll_release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The new router was polled right after the tick, without the clock
    # advancing to the refresh debounce.
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subentry_removed_releases_its_stamps(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a router subentry releases its stamps and keeps its trackers."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    phone_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    laptop_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert hass.states.get(phone_id).state == STATE_HOME
    assert hass.states.get(laptop_id).state == STATE_HOME

    subentry_b = next(
        subentry
        for subentry in two_router_hub.subentries.values()
        if subentry.data[CONF_HOST] == MOCK_HOST_B
    )
    hass.config_entries.async_remove_subentry(two_router_hub, subentry_b.subentry_id)
    await hass.async_block_till_done()

    # The entry stays loaded with its remaining router.
    assert two_router_hub.state is ConfigEntryState.LOADED
    assert len(two_router_hub.subentries) == 1

    # The trackers and devices stay registered to the hub; nothing moves.
    assert (
        entity_registry.async_get(laptop_id).config_entry_id == two_router_hub.entry_id
    )
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_LAPTOP), two_router_hub.entry_id
    )
    # The laptop's stamps were released with its router, so it is
    # unavailable, while the remaining router still reports the phone.
    assert hass.states.get(laptop_id).state == STATE_UNAVAILABLE
    assert hass.states.get(phone_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_disabling_entry_disables_trackers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling the hub disables all of its trackers."""
    _mock, ubus = mock_ubus_by_host
    mock_config_entry.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_registry.async_get(entity_id).disabled_by is None

    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.CONFIG_ENTRY
    )


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_ubus_client_construction(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the ubus client uses the subentry's scheme and verification."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[
            router_subentry_data(
                {**MOCK_CONFIG, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl}
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
        timeout=REQUEST_TIMEOUT.total_seconds(),
    )


async def test_ubus_client_defaults_without_ssl_options(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a subentry without the SSL options defaults to HTTP and verification."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    data = dict(subentry.data)
    del data[CONF_SSL]
    del data[CONF_VERIFY_SSL]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_subentry(mock_config_entry, subentry, data=data)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_ubus.assert_called_once_with(
        f"http://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=True,
        timeout=REQUEST_TIMEOUT.total_seconds(),
    )


async def test_session_refreshed_after_permission_error(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dropped session is re-authenticated and the scan retried."""
    mock_ubus.return_value.get_hostapd_clients.side_effect = [
        PermissionError,
        {
            "clients": {
                MAC_PHONE: {"authorized": True},
                MAC_LAPTOP: {"authorized": True},
            }
        },
        {"clients": {}},
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_ubus.return_value.connect.call_count == 2
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}


async def test_unload_entry(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "enabled", [pytest.param(False, id="disabled"), pytest.param(True, id="enabled")]
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    """Test only a client which is not connected can be removed."""
    monkeypatch.setattr(
        UbusScannerEntity, "_attr_entity_registry_enabled_default", enabled
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    connection = (dr.CONNECTION_NETWORK_MAC, MAC_PHONE)
    device_entry = device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    assert device_entry is not None

    response = await ws_client.remove_device(device_entry.id)
    assert not response["success"]
    assert device_registry.async_get(device_entry.id)

    clients = mock_ubus.return_value.get_hostapd_clients
    connected = clients.side_effect
    clients.side_effect = lambda interface: {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    # The client stays connected for CONSIDER_HOME after its last stamp,
    # so it can only be removed once that stamp has aged out.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    response = await ws_client.remove_device(device_entry.id)
    assert response["success"]
    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)

    # A removed client is tracked again when it reconnects.
    clients.side_effect = connected
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)
    assert entity_id is not None
    assert (hass.states.get(entity_id) is not None) is enabled


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing an unexpected child device is rejected."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    parent_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "parent")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "child")},
        parent_device_id=parent_device.id,
    )
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(child_device.id)

    assert not response["success"]
    assert device_registry.async_get(child_device.id)


async def test_remove_device_of_unloaded_entry(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a client device can be removed while the entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    assert device_entry is not None
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(device_entry.id)

    assert response["success"]
    assert not device_registry.async_get(device_entry.id)
