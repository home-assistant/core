"""Tests for the OpenWrt (ubus) device tracker."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.ubus.const import DOMAIN
from homeassistant.components.ubus.coordinator import LEASE_REREAD_INTERVAL
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntries,
    ConfigEntryError,
    ConfigEntryState,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
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
    MAC_GUEST,
    MAC_LAPTOP,
    MAC_PHONE,
    MOCK_CONFIG,
    MOCK_HOST,
    MOCK_HOST_B,
)


@pytest.mark.parametrize(
    ("dhcp_software", "expected_names"),
    [
        pytest.param(
            "dnsmasq", {MAC_PHONE: "my-phone", MAC_LAPTOP: "my-laptop"}, id="dnsmasq"
        ),
        pytest.param(
            "odhcpd", {MAC_PHONE: "my-phone", MAC_LAPTOP: "my-laptop"}, id="odhcpd"
        ),
        pytest.param("none", {MAC_PHONE: MAC_PHONE, MAC_LAPTOP: MAC_LAPTOP}, id="none"),
    ],
)
async def test_only_authorized_clients_are_tracked(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    expected_names: dict[str, str],
) -> None:
    """Test that authorized clients become entities and names resolve per backend."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}
    assert MAC_GUEST not in {e.unique_id for e in entries}
    assert {e.original_name for e in entries} == {None}
    devices = {e.unique_id: device_registry.async_get(e.device_id) for e in entries}
    assert {mac: device.name for mac, device in devices.items()} == expected_names
    assert {mac: device.connections for mac, device in devices.items()} == {
        mac: {(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))} for mac in expected_names
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_source_attribute_is_reporting_host(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the source attribute identifies the router the device is connected to."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for mac in (MAC_PHONE, MAC_LAPTOP):
        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, mac
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["source"] == MOCK_HOST

    mock_ubus.return_value.get_hostapd_clients.return_value["clients"][MAC_LAPTOP][
        "authorized"
    ] = False
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    laptop = hass.states.get(
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP)
    )
    assert laptop is not None
    assert laptop.state == STATE_NOT_HOME
    # No router reports the device, so the source attribute is dropped.
    assert "source" not in laptop.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_single_tracker_for_multiple_routers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client roaming between routers keeps a single shared tracker.

    Multi-AP roaming must not create a duplicate tracker per router; the
    source attribute follows the router which currently sees the client.
    """
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    phone_leases = {"data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *"}
    ubus[MOCK_HOST].file_read.return_value = phone_leases
    ubus[MOCK_HOST_B].file_read.return_value = phone_leases
    # The device is connected to router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST
    assert state.attributes["host_name"] == "my-phone"
    # One device for the MAC, registered by the entry which first saw it.
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_a.entry_id
    )
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_b.entry_id
    )
    assert not er.async_entries_for_config_entry(entity_registry, entry_b.entry_id)

    # The device moves to router B; the same tracker is sourced from B.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_b.entry_id
    )

    # The device disconnects from every router.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_roaming_device_stays_on_single_tracker(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device seen by both routers while roaming stays connected.

    During a handover the old and the new AP report the same client for a
    while; when the old AP drops it, only the new AP keeps the tracker
    connected, since a router may only release a client it last reported.
    """
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    leases = {"data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *"}
    ubus[MOCK_HOST].file_read.return_value = leases
    ubus[MOCK_HOST_B].file_read.return_value = leases
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # The device is seen by both routers while it roams.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    # Whoever refreshed last is the reported source while both see the device.
    assert state.attributes["source"] in (MOCK_HOST, MOCK_HOST_B)

    # Router A loses the device; router B keeps reporting it.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_kept_when_owner_entry_reloaded(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the owner keeps reporting a client connected to another router."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The device moves to router B, then entry A is reloaded.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert await hass.config_entries.async_unload(entry_a.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # Entry A no longer sees the device but still owns and reports the tracker.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unload_entry_releases_client_claims(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading a router entry stops it from reporting clients."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The device moves to router B.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source"] == MOCK_HOST_B

    # Unloading entry B stops the device being reported.
    assert await hass.config_entries.async_unload(entry_b.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert "source" not in state.attributes

    # Reloading entry B reports the device again.
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


async def test_late_refresh_after_unload_is_ignored(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a refresh finishing after an unload doesn't restore its clients."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is reported by router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The coordinator is captured before the entry is unloaded, as its
    # runtime_data is removed from the entry on unload.
    coordinator_a = entry_a.runtime_data
    assert await hass.config_entries.async_unload(entry_a.entry_id)
    await hass.async_block_till_done()

    # A refresh which was in flight during the unload now finishes; its
    # results are ignored, so the released reports are not restored.
    await coordinator_a._async_update_data()
    coordinator_a._async_refresh_finished()

    assert MOCK_HOST not in hass.data[DOMAIN].reports.get(MAC_PHONE, {})


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unloading_router_with_no_reports_updates_trackers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading a router without reports still updates remaining trackers."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The device also connects to router B, then leaves router A.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B

    # Router B becomes unreachable, clearing its reports.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Unloading router B, which has no reports left, still updates the
    # remaining tracker, which is available again without router B.
    assert await hass.config_entries.async_unload(entry_b.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_failed_unload_keeps_client_reported(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a failed unload leaves the router reporting its clients."""
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

    # The platform unload fails, so the entry stays loaded and reporting.
    with patch.object(
        ConfigEntries, "async_unload_platforms_or_raise", side_effect=ConfigEntryError
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_handed_to_other_entry_on_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the remaining entry takes over a tracker when the owner is removed."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == entry_a.entry_id

    # The device moves to router B, then entry A is removed.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.config_entries.async_remove(entry_a.entry_id)
    await hass.async_block_till_done()

    # Entry B takes over the tracker, with its own device for the client.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == entry_b.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_b.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_rehomed_when_owning_entry_cannot_report(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a healthy router takes over a tracker after the owner is offline."""
    _mock, _ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    # The client was last seen on router A, so its tracker and device are
    # owned by entry A in the persisted registries.
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry_a,
        device_id=device.id,
    )

    # Router A is offline, so its entry awaits a setup retry after the
    # restart; router B is healthy and reports the client.
    router_a = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router_a.connect.side_effect = ConnectionError
    router_b = _mock(f"http://{MOCK_HOST_B}/ubus", "root", "password", verify=True)
    router_b.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }

    # Setting up either entry loads the integration and sets up both: A's
    # entry can't load because its router is offline, B's can.
    assert not await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()
    assert entry_a.state is ConfigEntryState.SETUP_RETRY
    assert entry_b.state is ConfigEntryState.LOADED

    # Entry B re-homed the tracker and its device, so it reports the client.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == entry_b.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_b.entry_id
    )
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_a.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_rediscovered_by_other_router_after_device_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test another entry recreates a tracker whose device was removed."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_a.entry_id
    )
    assert device is not None

    # The device leaves router A and is removed from the registry.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_registry.async_remove_device(device.id)
    await hass.async_block_till_done()

    # The client reconnects to router B only, so entry B must recreate it.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == entry_b.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_rediscovered_by_other_router_after_entity_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test another entry recreates a tracker whose entity was removed."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_HOME

    # The device leaves router A and its tracker is removed, leaving
    # the device in the registry.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_a.entry_id
    )

    # The client reconnects to router B only, so entry B must recreate it.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == entry_b.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_b.entry_id
    )
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), entry_a.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_unavailable_while_reporting_router_unreachable(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the tracker is unavailable while the reporting router is unreachable."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The device moves to router B, then router B becomes unreachable.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B

    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Router B recovers and reports the device again.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_unavailable_while_entry_in_setup_retry(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unavailable tracker recovers when the router's setup retry succeeds."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    # Router B cannot be read, so its entry awaits a setup retry.
    router_b = _mock(f"http://{MOCK_HOST_B}/ubus", "root", "password", verify=True)

    def _connect() -> str:
        router_b.session_id = "session-id"
        return "session-id"

    router_b.connect.side_effect = ConnectionError

    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()
    assert entry_b.state is ConfigEntryState.SETUP_RETRY

    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # The device leaves router A; router B still awaits a setup retry.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Router B recovers with no clients; the tracker becomes available
    # without waiting for router A's next poll.
    router_b.connect.side_effect = _connect
    freezer.tick(timedelta(seconds=21))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry_b.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_available_after_unreachable_router_recovers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the tracker becomes available when an unreachable router recovers."""
    _mock, ubus = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    # The device is on router A, so entry A owns its tracker.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # The device leaves router A while router B cannot be read.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    router_b = _mock(f"http://{MOCK_HOST_B}/ubus", "root", "password", verify=True)
    router_b.get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Router B recovers with no clients; the tracker becomes available
    # without router A reporting anything new.
    router_b.get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.parametrize(
    ("yaml_ssl", "expected"),
    [
        pytest.param({}, {CONF_SSL: False, CONF_VERIFY_SSL: True}, id="defaults"),
        pytest.param(
            {CONF_SSL: True},
            {CONF_SSL: True, CONF_VERIFY_SSL: True},
            id="ssl_verified_by_default",
        ),
        pytest.param(
            {CONF_SSL: True, CONF_VERIFY_SSL: False},
            {CONF_SSL: True, CONF_VERIFY_SSL: False},
            id="ssl_unverified",
        ),
        pytest.param(
            {CONF_SSL: True, CONF_VERIFY_SSL: True},
            {CONF_SSL: True, CONF_VERIFY_SSL: True},
            id="ssl_verified",
        ),
    ],
)
async def test_setup_scanner_imports_yaml(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    yaml_ssl: dict[str, bool],
    expected: dict[str, bool],
) -> None:
    """Test the legacy YAML platform imports itself into a config entry."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {
                    "platform": DOMAIN,
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: "root",
                    CONF_PASSWORD: "password",
                    **yaml_ssl,
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == {**MOCK_CONFIG, **expected}


async def test_setup_scanner_creates_issue_on_cannot_connect(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is raised when the YAML import cannot connect."""
    mock_ubus.return_value.connect.side_effect = TypeError

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {
                    "platform": DOMAIN,
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: "root",
                    CONF_PASSWORD: "password",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_placeholders == {"host": MOCK_HOST}


@pytest.mark.parametrize(
    ("dhcp_software", "method"),
    [
        pytest.param("dnsmasq", "file_read", id="dnsmasq"),
        pytest.param("odhcpd", "get_dhcp_method", id="odhcpd"),
    ],
)
async def test_missing_leases_keep_existing_device_name(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    method: str,
) -> None:
    """Test an empty lease read names only new devices after their MAC."""
    getattr(mock_ubus.return_value, method).return_value = None
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
        name="my-phone",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    laptop = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_LAPTOP), mock_config_entry.entry_id
    )
    assert phone is not None
    assert phone.name == "my-phone"
    assert laptop is not None
    assert laptop.name == MAC_LAPTOP


@pytest.mark.parametrize(
    "enabled", [pytest.param(False, id="disabled"), pytest.param(True, id="enabled")]
)
@pytest.mark.parametrize(
    "initial_leases",
    [
        pytest.param(None, id="empty_read"),
        pytest.param({"data": ""}, id="no_leases"),
        pytest.param(
            {"data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 * *"},
            id="unknown_hostname",
        ),
    ],
)
async def test_device_renamed_when_hostname_appears(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    initial_leases: dict[str, Any] | None,
    enabled: bool,
) -> None:
    """Test a client without a known hostname is renamed once it has one."""
    monkeypatch.setattr(
        UbusScannerEntity, "_attr_entity_registry_enabled_default", enabled
    )
    file_read = mock_ubus.return_value.file_read
    leases = file_read.return_value
    file_read.return_value = initial_leases
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert (hass.states.get(entity_id) is not None) is enabled
    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    assert phone is not None
    assert phone.name == MAC_PHONE

    file_read.return_value = leases
    freezer.tick(LEASE_REREAD_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    phone = device_registry.async_get(phone.id)
    assert phone is not None
    assert phone.name == "my-phone"

    # The leases are not reread once every client has a hostname.
    read_count = file_read.call_count
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert file_read.call_count == read_count


async def test_disabled_trackers_not_recreated(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trackers which are disabled by default are only created once."""
    mock_config_entry.add_to_hass(hass)
    with patch.object(
        UbusScannerEntity,
        "__init__",
        autospec=True,
        side_effect=UbusScannerEntity.__init__,
    ) as mock_init:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for _ in range(3):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_init.call_count == 2
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {e.disabled_by for e in entries} == {er.RegistryEntryDisabler.INTEGRATION}


async def test_other_entry_device_removal_keeps_tracking(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing another entry's device for a tracked MAC is ignored."""
    mock_config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    with patch.object(
        UbusScannerEntity,
        "__init__",
        autospec=True,
        side_effect=UbusScannerEntity.__init__,
    ) as mock_init:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        device_registry.async_remove_device(other_device.id)
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_init.call_count == 2


async def test_lease_reread_throttled_for_clients_without_hostname(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the leases are reread for new clients, else only periodically."""
    file_read = mock_ubus.return_value.file_read
    file_read.return_value = {
        "data": (
            "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *\n"
            "1600000000 11:22:33:44:55:66 192.168.1.11 * *"
        )
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert file_read.call_count == 1

    for _ in range(3):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert file_read.call_count == 1

    freezer.tick(LEASE_REREAD_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert file_read.call_count == 2

    mock_ubus.return_value.get_hostapd_clients.return_value["clients"][MAC_GUEST][
        "authorized"
    ] = True
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert file_read.call_count == 3


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_empty_lease_reread_keeps_known_hostnames(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lease reread without a known client keeps its hostname."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A new client without a hostname triggers a reread, which is empty.
    file_read = mock_ubus.return_value.file_read
    file_read.return_value = {"data": ""}
    mock_ubus.return_value.get_hostapd_clients.return_value["clients"][MAC_GUEST][
        "authorized"
    ] = True
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert file_read.call_count == 2
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["host_name"] == "my-phone"
    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    assert phone is not None
    assert phone.name == "my-phone"
