"""Tests for the OpenWrt (ubus) device tracker."""

import asyncio
from datetime import timedelta
import threading
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import DOMAIN, SUBENTRY_TYPE_ROUTER
from homeassistant.components.ubus.coordinator import LEASE_REREAD_INTERVAL
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntries,
    ConfigEntryDisabler,
    ConfigEntryError,
    ConfigEntryState,
    ConfigSubentry,
    UnknownEntry,
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
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    MAC_GUEST,
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
async def test_client_present_when_authorized_on_one_interface(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a client appears to be "home" when authorized on at least one interface."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_HOME


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

    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    laptop = hass.states.get(
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP)
    )
    assert laptop is not None
    # The laptop's last stamp is still within CONSIDER_HOME, so it stays
    # home.
    assert laptop.state == STATE_HOME
    assert laptop.attributes["source"] == MOCK_HOST

    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    laptop = hass.states.get(
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP)
    )
    assert laptop is not None
    # Once the stamps age out, no router reports the device, so the source
    # attribute is dropped.
    assert laptop.state == STATE_NOT_HOME
    assert "source" not in laptop.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_single_tracker_for_multiple_routers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client roaming between routers keeps a single tracker.

    Multi-AP roaming must not create a duplicate tracker per router; the
    source attribute follows the router which currently sees the client.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    phone_leases = {"data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *"}
    ubus[MOCK_HOST].file_read.return_value = phone_leases
    ubus[MOCK_HOST_B].file_read.return_value = phone_leases
    # The device is connected to router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST
    assert state.attributes["host_name"] == "my-phone"
    # One tracker for the MAC, with its device registered to the hub.
    trackers = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == DEVICE_TRACKER_DOMAIN and entry.platform == DOMAIN
    ]
    assert len(trackers) == 1
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), two_router_hub.entry_id
    )

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

    # The device disconnects from every router, but the tracker stays
    # home while the stamps are recent.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B

    # Once the stamps age out of CONSIDER_HOME, the tracker leaves.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_mac_address_case_normalized_across_routers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test routers reporting the same MAC in different case share one tracker.

    MAC addresses are normalized to lowercase at the source, so however
    a router spells the address, the client gets one tracker under its
    normalized form.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # Router A reports the MAC uppercase, router B lowercase.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE.upper(): {"authorized": True}}
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    # One tracker for the client, under its normalized MAC.
    trackers = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == DEVICE_TRACKER_DOMAIN and entry.platform == DOMAIN
    ]
    assert len(trackers) == 1
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE.upper()
        )
        is None
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_uppercase_unique_id_migrated_to_lowercase(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a tracker created before MAC normalization keeps its entity id.

    A router which reported the MAC in another case created the tracker
    under that raw unique id; it is re-pointed to the normalized form on
    setup, so the entity and its customizations are reused.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    # The tracker and device were created before MACs were normalized, so
    # they carry the router's raw case.
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE.upper())},
    )
    entity_entry = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
    )
    entity_id = entity_entry.entity_id

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The tracker was reused with its entity id, now under the normalized
    # unique id.
    assert entity_registry.async_get(entity_id) is not None
    assert entity_registry.async_get(entity_id).unique_id == MAC_PHONE
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE.upper()
        )
        is None
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_duplicate_mac_case_trackers_merged(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the established tracker wins when both MAC cases are registered.

    If a tracker exists in both the raw case and the normalized form, the
    established one keeps its entity id and gains the normalized unique id,
    and the duplicate is removed.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE.upper())},
    )
    raw_entry = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
    )
    raw_id = raw_entry.entity_id
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=device.id,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The established tracker kept its entity id and gained the normalized
    # unique id; the duplicate is gone.
    assert entity_registry.async_get(raw_id) is not None
    assert entity_registry.async_get(raw_id).unique_id == MAC_PHONE
    trackers = [
        registry_entry
        for registry_entry in entity_registry.entities.values()
        if registry_entry.domain == DEVICE_TRACKER_DOMAIN
        and registry_entry.platform == DOMAIN
    ]
    assert len(trackers) == 1
    state = hass.states.get(raw_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enabled_tracker_wins_over_disabled_duplicate(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an enabled tracker wins over a disabled duplicate of the other case.

    The established, enabled tracker keeps its entity id and settings,
    while the disabled duplicate created in the other MAC case is removed.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    # The established tracker exists under the normalized unique id and is
    # enabled with a user-provided name.
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    established = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=device.id,
        disabled_by=None,
    )
    entity_registry.async_update_entity(established.entity_id, name="Phone")
    # A duplicate in the raw case was created later and is disabled.
    duplicate = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The enabled tracker kept its entity id and settings; the disabled
    # duplicate is gone.
    assert entity_registry.async_get(established.entity_id) is not None
    assert entity_registry.async_get(established.entity_id).disabled_by is None
    assert entity_registry.async_get(established.entity_id).name == "Phone"
    assert entity_registry.async_get(duplicate.entity_id) is None

    state = hass.states.get(established.entity_id)
    assert state is not None
    assert state.state == STATE_HOME


async def test_unique_id_normalization_defers_when_other_entry_owns_the_id(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a raw-case tracker is not renamed or rediscovered while another entry owns the id.

    A failed migration or a newer-schema entry may hold the normalized
    unique id; the registry would raise on the rename and abort the
    whole platform, so the tracker keeps its raw-case id then, and a
    live sighting must not re-assign the other entry's tracker.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)
    # A newer-schema entry which the consolidation leaves in place.
    other = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        version=3,
        entry_id="00000000000000000000000000B",
    )
    other.add_to_hass(hass)
    # The other entry already owns the normalized unique id; this
    # entry's tracker was created before MACs were normalized.
    other_tracker = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=other,
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE.upper())},
    )
    raw_entry = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {"clients": {}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The rename was deferred: the tracker keeps the raw-case unique id
    # and its platform loaded, while the other entry's tracker is
    # untouched. The state proves the platform completed; a failed
    # rename aborts it and leaves no tracker state behind.
    assert entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get(raw_entry.entity_id) is not None
    assert entity_registry.async_get(raw_entry.entity_id).unique_id == MAC_PHONE.upper()
    assert entity_registry.async_get(other_tracker.entity_id) is not None
    assert hass.states.get(raw_entry.entity_id) is not None

    # A live sighting must not create or re-assign the entity the other
    # entry owns; this entry's tracker still reports the client.
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        entity_registry.async_get(other_tracker.entity_id).config_entry_id
        == other.entry_id
    )
    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE)
        == other_tracker.entity_id
    )
    state = hass.states.get(raw_entry.entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_duplicate_tracker_removal_repoints_storage_persons(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a referenced duplicate tracker is removed without deferral.

    The storage person is re-pointed at the surviving tracker, while
    the YAML person and the device automation keep pointing at the
    removed duplicate, as the breaking change discloses.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    # The established tracker exists in the raw case, as created before
    # MAC normalization, on its own device; the duplicate's device is
    # identified without the MAC connection, so it does not collapse
    # into the survivor's.
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    established = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
    )
    duplicate_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MAC_PHONE)},
    )
    duplicate = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=duplicate_device.id,
    )
    await async_setup_component(
        hass,
        PERSON_DOMAIN,
        {
            PERSON_DOMAIN: [
                {
                    "id": "yaml_person",
                    "name": "Yaml person",
                    "device_trackers": [duplicate.entity_id],
                }
            ]
        },
    )
    person = await hass.data[PERSON_DOMAIN].storage_collection.async_create_item(
        {"name": "Storage person", "device_trackers": [duplicate.entity_id]}
    )
    await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "Duplicate device automation",
                    "trigger": [
                        {
                            "platform": "device",
                            "device_id": duplicate_device.id,
                            "domain": DEVICE_TRACKER_DOMAIN,
                            "entity_id": duplicate.entity_id,
                            "type": "enters",
                            "zone": "zone.home",
                        }
                    ],
                    "action": [{"stop": "done"}],
                }
            ]
        },
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The duplicate and its device are removed despite the references;
    # no repair is raised, as the breaking change covers them.
    assert entity_registry.async_get(duplicate.entity_id) is None
    assert device_registry.async_get(duplicate_device.id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"dedup_referenced_{duplicate.unique_id}"
        )
        is None
    )
    # The YAML person is untouched, and the storage person was
    # re-pointed at the surviving tracker, so it keeps tracking the
    # client.
    assert hass.data[PERSON_DOMAIN].yaml_collection.async_items()[0][
        "device_trackers"
    ] == [duplicate.entity_id]
    storage_person = next(
        item
        for item in hass.data[PERSON_DOMAIN].storage_collection.async_items()
        if item["id"] == person["id"]
    )
    assert storage_person["device_trackers"] == [established.entity_id]
    assert hass.states.get("person.storage_person").state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migration_device_merge_removes_duplicate_tracker(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a merged legacy device and its referenced tracker are removed.

    The legacy entry is removed either way, so its device automations
    cannot be re-pointed with their device; the duplicate tracker is
    removed with the merge and the person follows the survivor, as the
    breaking change discloses.
    """
    _mock, ubus = mock_ubus_by_host
    hub = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    hub.add_to_hass(hass)
    # A legacy entry tracking the same client, with its own device and a
    # raw-case tracker which survives the migration unload.
    legacy = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy.add_to_hass(hass)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=hub.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    device_registry.async_update_device(hub_device.id, name_by_user="Phone")
    established = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=hub,
        device_id=hub_device.id,
    )
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=legacy.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    legacy_tracker = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=legacy,
        device_id=legacy_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await async_setup_component(hass, PERSON_DOMAIN, {})
    person = await hass.data[PERSON_DOMAIN].storage_collection.async_create_item(
        {"name": "Phone", "device_trackers": [legacy_tracker.entity_id]}
    )
    await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "Legacy device automation",
                    "trigger": [
                        {
                            "platform": "device",
                            "device_id": legacy_device.id,
                            "domain": DEVICE_TRACKER_DOMAIN,
                            "entity_id": legacy_tracker.entity_id,
                            "type": "enters",
                            "zone": "zone.home",
                        }
                    ],
                    "action": [{"stop": "done"}],
                }
            ]
        },
    )

    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(hub.entry_id)
    await hass.async_block_till_done()

    # The legacy device was merged into the established one and the
    # duplicate tracker was removed with it; no repair is raised for
    # the broken device automation, and the person follows the
    # survivor.
    assert hub.state is ConfigEntryState.LOADED
    assert device_registry.async_get(legacy_device.id) is None
    assert entity_registry.async_get(legacy_tracker.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"migration_device_references_{legacy_device.id}"
        )
        is None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"dedup_referenced_{legacy_tracker.unique_id}"
        )
        is None
    )
    storage_person = next(
        item
        for item in hass.data[PERSON_DOMAIN].storage_collection.async_items()
        if item["id"] == person["id"]
    )
    assert storage_person["device_trackers"] == [established.entity_id]
    assert hass.states.get("person.phone").state == STATE_HOME
    trackers = [
        registry_entry
        for registry_entry in entity_registry.entities.values()
        if registry_entry.domain == DEVICE_TRACKER_DOMAIN
        and registry_entry.platform == DOMAIN
    ]
    assert len(trackers) == 1
    assert {tracker.config_entry_id for tracker in trackers} == {hub.entry_id}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_ungrounded_clients_use_normalized_mac(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the ungrounded check normalizes a raw-case tracker's MAC.

    While MAC normalization is deferred, the tracker keeps its raw-case
    unique id; its absence is established once its last router stops
    monitoring, so it must stay unavailable rather than away.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)
    # A newer-schema entry which the consolidation leaves in place owns
    # the normalized unique id, so this entry's tracker keeps its raw
    # case.
    other = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        version=3,
        entry_id="00000000000000000000000000B",
    )
    other.add_to_hass(hass)
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=other,
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE.upper())},
    )
    raw_entry = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(raw_entry.entity_id).state == STATE_HOME

    # Removing the only router leaves no monitor for the client.
    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    await hass.async_block_till_done()
    assert hass.states.get(raw_entry.entity_id).state == STATE_UNAVAILABLE

    # A healthy replacement router sees no clients; the phone was last
    # seen on a router which is no longer monitored.
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(MOCK_HOST_CONFIG_B),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=MOCK_HOST_B,
            unique_id=MOCK_HOST_B,
        ),
    )
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(raw_entry.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_derived_disabled_tracker_wins_over_disabled_duplicate(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker disabled only by its entry wins over a disabled duplicate.

    A tracker the user enabled carries the disabled state of its
    temporarily disabled config entry; the migration must not delete it in
    favor of an older integration-disabled duplicate.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    # The older duplicate was created by the previous implementation under
    # the raw-case unique id and is disabled by default.
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE.upper())},
    )
    duplicate = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    freezer.tick(timedelta(hours=1))
    # The user enabled the normalized tracker while the entry is disabled,
    # so it carries the entry's disabled state until the entry is re-enabled.
    established = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=device.id,
        disabled_by=None,
    )
    assert established.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    # Re-enabling the entry sets it up and clears the derived disabled
    # state.
    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()

    # The user-enabled tracker survived; the older disabled duplicate is
    # gone.
    assert entity_registry.async_get(duplicate.entity_id) is None
    assert entity_registry.async_get(established.entity_id) is not None
    assert entity_registry.async_get(established.entity_id).disabled_by is None

    state = hass.states.get(established.entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_duplicate_device_merged_into_survivors_device(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device left behind by a duplicate tracker is kept on the survivor.

    If the duplicate's device carries the client's name, area and
    automation references, the survivor must be re-attached to it instead
    of a fresh device.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    # The established tracker was created before MACs were normalized,
    # without a device.
    survivor = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
    )
    freezer.tick(timedelta(hours=1))
    # The duplicate and its device were created under the normalized case.
    duplicate_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
        name="Phone",
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=duplicate_device.id,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The duplicate tracker is gone; the survivor kept its entity id and
    # gained the duplicate's device.
    assert entity_registry.async_get(survivor.entity_id) is not None
    assert entity_registry.async_get(survivor.entity_id).unique_id == MAC_PHONE
    assert (
        entity_registry.async_get(survivor.entity_id).device_id == duplicate_device.id
    )
    assert device_registry.async_get(duplicate_device.id).name == "Phone"

    state = hass.states.get(survivor.entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_merge_preserves_disabled_entity_on_duplicate_device(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a disabled tracker on the duplicate device survives the merge.

    A duplicate device can host other trackers, for example left behind by
    a previously shared device; the unique id migration must not delete
    their registry entries, so the disabled ones keep their settings.
    """
    _mock, _ = mock_ubus_by_host
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[router_subentry_data(MOCK_CONFIG)],
    )
    entry.add_to_hass(hass)

    survivor = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=entry,
    )
    freezer.tick(timedelta(hours=1))
    duplicate_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
        name="Phone",
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=entry,
        device_id=duplicate_device.id,
    )
    # The duplicate device also hosts a tracker for another client,
    # which the user disabled.
    disabled = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_LAPTOP,
        config_entry=entry,
        device_id=duplicate_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    router = _mock(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
    router.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The duplicate tracker is gone; the survivor kept its entity id and
    # gained the duplicate's device.
    assert entity_registry.async_get(disabled.entity_id) is not None
    assert (
        entity_registry.async_get(disabled.entity_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )
    assert (
        entity_registry.async_get(survivor.entity_id).device_id == duplicate_device.id
    )
    assert device_registry.async_get(duplicate_device.id).name == "Phone"

    state = hass.states.get(survivor.entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_roaming_device_stays_on_single_tracker(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device seen by both routers while roaming stays connected.

    During a handover the old and the new AP report the same client for a
    while; when the old AP drops it, only the new AP's stamp keeps the
    tracker connected.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    leases = {"data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *"}
    ubus[MOCK_HOST].file_read.return_value = leases
    ubus[MOCK_HOST_B].file_read.return_value = leases
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

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
async def test_hostname_retained_when_router_has_no_lease(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the hostname survives roaming to a router without a lease.

    A router without a DHCP lease stamps no hostname; the hostname the
    client was last known by on another router is retained instead of
    dropping the host_name attribute.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # Router A knows the phone's hostname from its DHCP leases; router B
    # has no leases at all.
    ubus[MOCK_HOST].file_read.return_value = {
        "data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *"
    }
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source"] == MOCK_HOST
    assert state.attributes["host_name"] == "my-phone"

    # The phone roams to router B, which has no lease for it.
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
    assert state.attributes["host_name"] == "my-phone"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dropped_client_goes_not_home_after_consider_home(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped client stays home while its last stamp is recent.

    The dropping router keeps polling after the client drops, but its
    polls do not extend the client's last stamp.
    """
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

    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # Once the stamp ages out of CONSIDER_HOME, the client is not home,
    # though the router is still reachable.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_slow_router_does_not_stretch_sighting_times(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test each router's stamps carry its poll's own observation time.

    The slow router is the first subentry, so its stamps would win the
    source by order alone; the observation times must decide instead.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        two_router_hub, options={CONF_CONSIDER_HOME: 5}
    )
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {
            MAC_PHONE: {"authorized": True},
            MAC_LAPTOP: {"authorized": True},
        }
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    slow_started = threading.Event()
    slow_release = threading.Event()
    fast_release = threading.Event()
    fast_observed = threading.Event()

    def slow_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Hold the response for twenty seconds, as a slow router.
        slow_started.set()
        slow_release.wait()
        return {"clients": {MAC_PHONE: {"authorized": True}}}

    def fast_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Hold the response until the test releases it.
        fast_release.wait()
        return {
            "clients": {
                MAC_PHONE: {"authorized": True},
                MAC_LAPTOP: {"authorized": True},
            }
        }

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = slow_read
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = fast_read

    # Start the next tick and hold both routers in flight.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    assert await hass.async_add_executor_job(slow_started.wait, 10)

    # Wait for the fast router's poll to be observed, so its sighting time
    # is fixed before the clock advances again.
    for host, poll in two_router_hub.runtime_data._inflight.items():
        if host.host == MOCK_HOST_B:
            poll.add_done_callback(lambda _: fast_observed.set())
    freezer.tick(timedelta(seconds=10))
    fast_release.set()
    assert await hass.async_add_executor_job(fast_observed.wait, 10)
    fast_seen = dt_util.utcnow()

    freezer.tick(timedelta(seconds=10))
    slow_release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    slow_seen = dt_util.utcnow()

    coordinator = two_router_hub.runtime_data
    subentry_ids = {
        subentry.data[CONF_HOST]: subentry.subentry_id
        for subentry in two_router_hub.subentries.values()
    }
    phone = coordinator.data[MAC_PHONE]
    # Each router's stamps carry its poll's own observation time.
    assert phone[subentry_ids[MOCK_HOST]].last_seen == slow_seen
    assert phone[subentry_ids[MOCK_HOST_B]].last_seen == fast_seen
    # The newest observation reports the source, not the subentry order.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source"] == MOCK_HOST
    # The laptop was last seen by the fast router only; the slow router's
    # late answer must not stretch its consider_home window.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subentry_removal_keeps_remaining_stamps(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing a router stops it from reporting its clients.

    The remaining router's last stamp keeps the tracker home until it
    ages out, while the entry itself stays loaded.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

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

    # Removing router B stops it from reporting the device, but the
    # tracker stays home while router A's last stamp is recent.
    subentry_b = next(
        subentry
        for subentry in two_router_hub.subentries.values()
        if subentry.data[CONF_HOST] == MOCK_HOST_B
    )
    hass.config_entries.async_remove_subentry(two_router_hub, subentry_b.subentry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # Once the stamp ages out, the device is no longer home.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_late_refresh_after_subentry_removal_is_ignored(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a refresh in flight during a subentry removal doesn't stamp its clients."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B

    # Router B's next poll is blocked in flight.
    poll_started = threading.Event()
    release = threading.Event()

    def _blocked_clients(interface: str) -> dict:
        poll_started.set()
        release.wait()
        return {"clients": {MAC_PHONE: {"authorized": True}}}

    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = _blocked_clients
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    # Wait for router B's poll to be in flight, then remove its subentry.
    try:
        assert await hass.async_add_executor_job(poll_started.wait, 10)
        subentry_b = next(
            subentry
            for subentry in two_router_hub.subentries.values()
            if subentry.data[CONF_HOST] == MOCK_HOST_B
        )
        hass.config_entries.async_remove_subentry(
            two_router_hub, subentry_b.subentry_id
        )
    finally:
        # The removal's refresh waits for the in-flight tick.
        release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The in-flight refresh finishes after the removal; its results are
    # ignored, so without a fresh stamp the tracker is unavailable.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("seen_on"),
    [
        pytest.param([MOCK_HOST, MOCK_HOST_B], id="seen_on_both_routers"),
        pytest.param([MOCK_HOST_B], id="seen_only_on_removed_router"),
    ],
)
async def test_removed_router_stamps_pruned_when_all_routers_fail(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    seen_on: list[str],
) -> None:
    """Test removing a router prunes its stamps even when all polls fail.

    A failed tick keeps the routers' old stamps, but the removed router's
    stamps must go with it: its health entry is removed, and a missing
    health defaults to healthy, which would keep its clients home.
    """
    _mock, ubus = mock_ubus_by_host
    for host in seen_on:
        ubus[host].get_hostapd_clients.return_value = {
            "clients": {MAC_PHONE: {"authorized": True}}
        }
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # Let router A's next poll fail and remove router B, so the tick is
    # an all-routers failure.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = ConnectionError
    subentry_b = next(
        subentry
        for subentry in two_router_hub.subentries.values()
        if subentry.data[CONF_HOST] == MOCK_HOST_B
    )
    hass.config_entries.async_remove_subentry(two_router_hub, subentry_b.subentry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Router A failed, so the phone's absence cannot be verified; the
    # removed router's stamps must not keep it home.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_in_flight_poll_ignored_for_reconfigured_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an in-flight poll is ignored when the subentry is reconfigured.

    Reconfiguration retains the subentry id, so the in-flight response from
    the old host must not stamp its clients as being on the new host.
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

    # The next poll is blocked in flight, and the subentry is reconfigured
    # to a different host while the poll is running.
    poll_started = threading.Event()
    release = threading.Event()

    def _blocked_clients(interface: str) -> dict:
        poll_started.set()
        release.wait()
        return {"clients": {MAC_PHONE: {"authorized": True}}}

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = _blocked_clients
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    # Wait for the poll to be in flight, then reconfigure the subentry.
    try:
        assert await hass.async_add_executor_job(poll_started.wait, 10)
        subentry = next(iter(mock_config_entry.subentries.values()))
        hass.config_entries.async_update_subentry(
            mock_config_entry, subentry, data=MOCK_HOST_CONFIG_C, title=MOCK_HOST_C
        )
    finally:
        # The reconfiguration's refresh waits for the in-flight tick.
        release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The in-flight result from the old host is ignored, so without a fresh
    # stamp from the new host the tracker is unavailable.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_timed_out_tick_reuses_in_flight_poll(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tick that times out re-awaits the in-flight poll on the next tick.

    The poll keeps running in the executor after the tick times out; a
    second poll for the same router would concurrently mutate its ubus
    session and lease state.

    The request timeout is zero for the ticks, so their timeouts are
    deterministic on the frozen clock: the poll is held in the executor
    between ticks and released before the final one.
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
    assert hass.states.get(entity_id).state == STATE_HOME
    assert ubus[MOCK_HOST].get_hostapd_clients.call_count == 1

    # The next poll blocks in the executor until it is released; the
    # request timeout is zero for the ticks, so their timeouts are
    # deterministic on the frozen clock.
    release = threading.Event()

    def _blocked_clients(interface: str) -> dict:
        release.wait()
        return {"clients": {MAC_PHONE: {"authorized": True}}}

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = _blocked_clients

    async def _run_tick() -> None:
        """Fire the next tick and await its refresh task.

        The refresh is the entry's background task; awaiting the entry's
        tasks, rather than all of them, keeps the wait from blocking on
        the in-flight executor poll, which is only released later. The
        ticks are 31 s apart, as the refresh timers are staggered up to
        half a second past the 30 s interval and must always be due.
        """
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await asyncio.wait(mock_config_entry._background_tasks)

    try:
        with patch(
            "homeassistant.components.ubus.coordinator.REQUEST_TIMEOUT",
            timedelta(),
        ):
            # The tick times out while the poll keeps running in the
            # executor; the failed tick marks the router unhealthy, so the
            # client's stamps stop counting until the next tick succeeds.
            await _run_tick()
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
            # The next tick must re-await the in-flight poll rather than
            # start a second one; it times out on the still-blocked poll.
            await _run_tick()
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
            # Releasing the poll settles it before the next tick runs,
            # which then applies its result.
            release.set()
            await hass.async_block_till_done(wait_background_tasks=True)
            await _run_tick()
    finally:
        release.set()

    # One poll ran at setup and one blocked, re-awaited by the later
    # ticks; a duplicate poll would have called the mock a third time.
    assert ubus[MOCK_HOST].get_hostapd_clients.call_count == 2
    assert hass.states.get(entity_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reobserved_poll_stamped_at_completion(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a re-observed poll is stamped when it finished, not the later tick.

    After a tick times out the in-flight poll keeps running; when a later
    tick re-observes it the sighting must be stamped at the poll's own
    completion, or the client would get a fresh consider_home window from
    the later refresh and outlive its absence.
    """
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CONSIDER_HOME: 5}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_HOME

    release = threading.Event()

    def _blocked_clients(interface: str) -> dict:
        release.wait()
        return {"clients": {MAC_PHONE: {"authorized": True}}}

    ubus[MOCK_HOST].get_hostapd_clients.side_effect = _blocked_clients

    async def _run_tick() -> None:
        """Fire the next tick and await its refresh task.

        Awaiting the entry's tasks, rather than all of them, keeps the
        wait from blocking on the in-flight executor poll, which is only
        released later. The ticks are 31 s apart, as the refresh timers
        are staggered up to half a second past the 30 s interval and must
        always be due.
        """
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await asyncio.wait(mock_config_entry._background_tasks)

    try:
        with patch(
            "homeassistant.components.ubus.coordinator.REQUEST_TIMEOUT",
            timedelta(),
        ):
            # The tick times out while the poll keeps running in the
            # executor; the failed tick marks the router unhealthy.
            await _run_tick()
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
            # The poll settles four seconds after the tick started; the
            # next tick re-observes it and must stamp that completion.
            freezer.tick(timedelta(seconds=4))
            release.set()
            await hass.async_block_till_done(wait_background_tasks=True)
            await _run_tick()
    finally:
        release.set()

    # The client was last seen four seconds after the timed-out tick; the
    # re-observing tick ran 31 s after that sighting, past the keep-home
    # window. A stamp at the re-observing tick would keep it home.
    assert hass.states.get(entity_id).state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_away_client_reports_not_home_after_restart(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client no router sees reports not home after a restart."""
    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_HOME

    # The client leaves and ages out of the keep-home window.
    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {}
    }
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    # The restart resets the presence; the restored tracker stays live and
    # the complete, healthy view establishes the client's absence.
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_away_client_unavailable_after_restart_while_router_down(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client stays unavailable after a restart while its router is down."""
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

    laptop_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert laptop_id is not None
    assert hass.states.get(laptop_id).state == STATE_HOME

    # Router B goes down, so the laptop's state is unverifiable.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(laptop_id).state == STATE_UNAVAILABLE

    # The restart resets the presence; the downed router might still see
    # the laptop, so it stays unavailable.
    assert await hass.config_entries.async_reload(two_router_hub.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(laptop_id).state == STATE_UNAVAILABLE

    # Router B answers again without the laptop; the complete view
    # establishes the absence.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = None
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(laptop_id).state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_last_router_removal_keeps_clients_ungrounded(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing the only router keeps its clients unavailable."""
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
    assert hass.states.get(entity_id).state == STATE_HOME

    # Removing the only router leaves no monitor; the state is
    # unverifiable.
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_remove_subentry(mock_config_entry, subentry.subentry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # A healthy replacement router sees no clients; the phone was last
    # seen on a router which is no longer monitored, so it stays
    # unavailable.
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType(MOCK_HOST_CONFIG_B),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=MOCK_HOST_B,
            unique_id=MOCK_HOST_B,
        ),
    )
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


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
async def test_tracker_rediscovered_after_device_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker whose device was removed is recreated when the client returns."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), two_router_hub.entry_id
    )
    assert device is not None

    # The device leaves router A and is removed from the registry.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_registry.async_remove_device(device.id)
    await hass.async_block_till_done()

    # The client reconnects to router B only, so the tracker is recreated.
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
    assert (
        entity_registry.async_get(entity_id).config_entry_id == two_router_hub.entry_id
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_rediscovered_after_entity_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker whose entity was removed is recreated when the client returns."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

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
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), two_router_hub.entry_id
    )

    # The client reconnects to router B only, so the tracker is recreated.
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
    assert (
        entity_registry.async_get(entity_id).config_entry_id == two_router_hub.entry_id
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), two_router_hub.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_removed_tracker_recreated_with_same_entity_id(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed tracker is recreated with its original entity ID."""
    _mock, ubus = mock_ubus_by_host
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
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
    assert hass.states.get(entity_id).state == STATE_HOME

    # The tracker is removed while the client is still connected, so it is
    # recreated and must reuse its entity ID.
    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE)
        == entity_id
    )
    assert hass.states.get(entity_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_unavailable_while_all_routers_unreachable(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the tracker is unavailable while every router is unreachable.

    The tracker is unavailable at once when the last reachable router
    fails, even while the client's stamps are still recent, and becomes
    home again when a router recovers and reports the client.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The device moves to router B, which then becomes unreachable.
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

    # Router A is still reachable, so the tracker is available, and the
    # device stays home on router A's recent stamp.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # Router A becomes unreachable too, so the tracker is unavailable at
    # once, even though the stamps are still recent.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = ConnectionError
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
async def test_tracker_unavailable_while_roamed_to_unreachable_router(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a roamed device is unavailable, not away, while unverifiable.

    The device demonstrably left the reachable router, so it must not be
    reported away while its freshest sighting is on a router which no
    longer updates.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # The device roams to router B, which then becomes unreachable.
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

    # Router B misses a poll; the device stays home on router A's recent
    # stamp while it is still recent.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST

    # Router A's stamp ages out; the device's freshest sighting is on the
    # unreachable router, so the tracker is unavailable rather than not
    # home.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes

    # Router B recovers and still reports the device.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_unavailable_while_sole_reporter_unreachable(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker is unavailable while only its reporting router is down.

    A healthy router which never saw the client holds no evidence about
    it, so the tracker is unavailable rather than not home while the
    reporting router misses polls.
    """
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router B only, so it is the sole reporter.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B

    # Router B misses a poll while router A stays reachable but has never
    # seen the device, so no healthy router can report it.
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
async def test_tracker_available_after_unreachable_router_recovers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the tracker becomes available when an unreachable router recovers."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)

    # The device is on router A.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

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
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The tracker is still available, because router A is reachable, and
    # the device stays home while the stamp is recent.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # Router A becomes unreachable too, so the tracker is unavailable at
    # once, even though the stamp is still recent.
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = ConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Router B recovers with no clients; since no healthy router has seen
    # the device, the tracker stays unavailable.
    ubus[MOCK_HOST_B].get_hostapd_clients.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Router A recovers once its stamp has aged out; the stale stamp
    # makes the tracker available again, reporting not home.
    freezer.tick(DEFAULT_CONSIDER_HOME)
    ubus[MOCK_HOST].get_hostapd_clients.side_effect = None
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
    """Test the legacy YAML platform imports itself into a hub entry."""
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
    assert entries[0].data == {}
    subentry = next(iter(entries[0].subentries.values()))
    assert dict(subentry.data) == {**MOCK_CONFIG, **expected}


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


async def test_missing_uci_config_falls_back_to_mac_names(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test clients are named by MAC while the dnsmasq uci config is missing."""
    mock_ubus.return_value.get_uci_config.return_value = None
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    assert phone is not None
    assert phone.name == MAC_PHONE
    laptop = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_LAPTOP), mock_config_entry.entry_id
    )
    assert laptop is not None
    assert laptop.name == MAC_LAPTOP

    # The hostnames are picked up on a later read once the config is available.
    mock_ubus.return_value.get_uci_config.return_value = {
        "values": {"cfg01": {"leasefile": "/var/dhcp/dnsmasq.leases"}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(phone.id).name == "my-phone"
    assert device_registry.async_get(laptop.id).name == "my-laptop"


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_renamed_when_latest_stamp_has_no_hostname(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    two_router_hub: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device is renamed from a hostname another router knows.

    The latest stamp comes from a router with no lease for the client,
    so the rename falls back to the hostname a previous stamp recorded.
    """
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].file_read.return_value = {
        "data": "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *\n"
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), two_router_hub.entry_id
    )
    assert phone is not None
    assert phone.name == MAC_PHONE

    # Router A now sees the phone and learns its hostname from its leases,
    # while the phone's latest stamp still comes from lease-less router B.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    phone = device_registry.async_get(phone.id)
    assert phone is not None
    assert phone.name == "my-phone"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_entity_service_refreshes_the_routers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update_entity re-polls the routers, while the trackers do not poll."""
    _mock, ubus = mock_ubus_by_host
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    phone_entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert phone_entity_id is not None
    assert hass.states.get(phone_entity_id).state == STATE_HOME

    # The laptop connected after the initial poll; the trackers do not
    # poll, so only a manual refresh surfaces it.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {
            MAC_PHONE: {"authorized": True},
            MAC_LAPTOP: {"authorized": True},
        }
    }
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": phone_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    laptop_entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert laptop_entity_id is not None
    assert hass.states.get(laptop_entity_id).state == STATE_HOME

    # Manual refreshes are debounced: a request for another tracker does
    # not poll the routers again within the debounce window.
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": laptop_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert ubus[MOCK_HOST].get_hostapd_clients.call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_recreated_when_client_returns_after_removal(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed tracker is recreated when its client returns.

    The client returns to the same router within consider_home, so its
    previous stamp keeps the state home; only the fresh sighting signals
    the discovery.
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

    # The client disconnects, and its tracker is removed while it is
    # absent; the stale stamp keeps the tracker home until it expires.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    # The client returns to the same router before the stamp expires.
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


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

    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {
            MAC_PHONE: {"authorized": True},
            MAC_LAPTOP: {"authorized": True},
            MAC_GUEST: {"authorized": True},
        }
    }
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
    mock_ubus.return_value.get_hostapd_clients.side_effect = lambda interface: {
        "clients": {
            MAC_PHONE: {"authorized": True},
            MAC_LAPTOP: {"authorized": True},
            MAC_GUEST: {"authorized": True},
        }
    }
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migration_merges_entries_into_hub(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test legacy entries are merged into the hub with their data as subentries."""
    _mock, ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    # A tracker and device the legacy entry created before the migration,
    # which runs in component setup, before any entry is set up.
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=legacy_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    entity = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=legacy_entry,
        device_id=legacy_device.id,
        disabled_by=None,
    )
    entity_id = entity.entity_id
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Only the hub remains, with a subentry per legacy router.
    assert hass.config_entries.async_entries(DOMAIN) == [hub_entry]
    assert hub_entry.data == {}
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }
    # The tracker was re-parented to the hub with the hub's device.
    assert entity_registry.async_get(entity_id).config_entry_id == hub_entry.entry_id
    assert device_registry.async_get(legacy_device.id) is not None
    assert device_registry.async_get(legacy_device.id).config_entry_id == (
        hub_entry.entry_id
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reenabled_entry_merges_into_late_hub(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entry re-enabled after a YAML import merges into the hub.

    With every entry disabled the startup consolidation has no hub to
    consolidate into, so the YAML import creates one; re-enabling an old
    entry must merge it into that hub instead of becoming a second
    poller, as it would be until the next restart.
    """
    _mock, ubus = mock_ubus_by_host
    legacy_a = MockConfigEntry(
        domain=DOMAIN,
        entry_id="00000000000000000000000000A",
        data=MOCK_CONFIG,
        title=MOCK_HOST,
    )
    legacy_a.disabled_by = ConfigEntryDisabler.USER
    legacy_a.add_to_hass(hass)
    legacy_b = MockConfigEntry(
        domain=DOMAIN,
        entry_id="00000000000000000000000000B",
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
    )
    legacy_b.disabled_by = ConfigEntryDisabler.USER
    legacy_b.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }

    # The YAML platform import creates the hub, as the startup
    # consolidation ran with every entry disabled.
    assert await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {
            DEVICE_TRACKER_DOMAIN: [
                {
                    "platform": DOMAIN,
                    CONF_HOST: MOCK_HOST_C,
                    CONF_USERNAME: "root",
                    CONF_PASSWORD: "password",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Host C's client appears on the hub's next poll, which the
    # re-enabled entry's transferred subentry triggers.
    ubus[MOCK_HOST_C].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 3
    hub = next(entry for entry in entries if entry.source == SOURCE_IMPORT)
    assert hub.state is ConfigEntryState.LOADED
    assert {subentry.unique_id for subentry in hub.subentries.values()} == {MOCK_HOST_C}
    assert legacy_a.disabled_by is ConfigEntryDisabler.USER
    assert legacy_b.disabled_by is ConfigEntryDisabler.USER

    # Re-enabling the old entry merges it into the hub instead of
    # leaving a second poller behind.
    await hass.config_entries.async_set_disabled_by(legacy_a.entry_id, None)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.entry_id for entry in entries] == [
        legacy_b.entry_id,
        hub.entry_id,
    ]
    assert {subentry.unique_id for subentry in hub.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_C,
    }
    # Both routers are polled on the hub; each client has exactly one
    # tracker, registered on the hub.
    for mac in (MAC_PHONE, MAC_LAPTOP):
        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, mac
        )
        assert entity_registry.async_get(entity_id).config_entry_id == hub.entry_id
        assert hass.states.get(entity_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("hub_customizations", "legacy_customizations", "expected"),
    [
        pytest.param(
            (None, None), (None, None), ("legacy", "hub"), id="both-uncustomized"
        ),
        pytest.param(
            ("Hub Phone", "hall"),
            (None, None),
            ("hub", "legacy"),
            id="hub-customized",
        ),
        pytest.param(
            (None, None),
            ("My Phone", "bedroom"),
            ("legacy", "hub"),
            id="legacy-customized",
        ),
    ],
)
async def test_migration_device_collision_keeps_established_device(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    hub_customizations: tuple[str | None, str | None],
    legacy_customizations: tuple[str | None, str | None],
    expected: tuple[str, str],
) -> None:
    """Test a device collision keeps the established device's id and data.

    The device the user named or placed in an area is kept over the
    other; when neither is customized the older one wins, so its id,
    name, area and automation references survive the merge.
    """
    _mock, ubus = mock_ubus_by_host
    area_ids = {
        name: area_registry.async_create(name).id for name in ("hall", "bedroom")
    }
    # The hub must be the lowest entry id so it runs the migration.
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    # A tracker and device the legacy entry created before the migration,
    # which runs in component setup, before any entry is set up.
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=legacy_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    device_registry.async_update_device(
        legacy_device.id,
        name_by_user=legacy_customizations[0],
        area_id=area_ids.get(legacy_customizations[1]),
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=legacy_entry,
        device_id=legacy_device.id,
        disabled_by=None,
    )
    hub_entry.add_to_hass(hass)
    # The hub already holds a device for the client.
    hub_device = device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    device_registry.async_update_device(
        hub_device.id,
        name_by_user=hub_customizations[0],
        area_id=area_ids.get(hub_customizations[1]),
    )

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    survivor_key, loser_key = expected
    devices = {"legacy": legacy_device, "hub": hub_device}
    customizations = {"legacy": legacy_customizations, "hub": hub_customizations}
    # The established device keeps its id and customizations.
    survivor = device_registry.async_get(devices[survivor_key].id)
    assert survivor is not None
    assert survivor.name_by_user == customizations[survivor_key][0]
    assert survivor.area_id == area_ids.get(customizations[survivor_key][1])
    assert device_registry.async_get(devices[loser_key].id) is None
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == devices[survivor_key].id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migration_device_collision_keeps_enabled_trackers_device(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test a device collision keeps the established tracker's device.

    The hub holds a disabled tracker with a normalized unique id and the
    legacy entry an enabled tracker with the pre-normalization case, so
    the legacy tracker survives the unique id migration; the merge must
    keep its customized device rather than delete it.
    """
    _mock, ubus = mock_ubus_by_host
    living_room = area_registry.async_create("living-room")
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    # Pre-migration state: the legacy tracker predates MAC normalization,
    # so its unique id and device keep the client's raw case.
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=legacy_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    device_registry.async_update_device(
        legacy_device.id,
        name_by_user="My Phone",
        area_id=living_room.id,
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE.upper(),
        config_entry=legacy_entry,
        device_id=legacy_device.id,
        disabled_by=None,
    )
    hub_entry.add_to_hass(hass)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        MAC_PHONE,
        config_entry=hub_entry,
        device_id=hub_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The legacy device survived the merge with its customizations and was
    # re-parented to the hub; the hub's device was deleted.
    assert device_registry.async_get(hub_device.id) is None
    device = device_registry.async_get(legacy_device.id)
    assert device is not None
    assert device.config_entry_id == hub_entry.entry_id
    assert device.name_by_user == "My Phone"
    assert device.area_id == living_room.id
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == legacy_device.id
    # The disabled hub tracker was removed by the unique id migration,
    # which lower-cased the surviving tracker's unique id.
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE.upper()
        )
        is None
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


async def test_migration_moves_device_without_tracker(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device whose tracker was deleted moves to the hub with the entry."""
    _mock, ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    for host in (MOCK_HOST, MOCK_HOST_B):
        ubus[host].get_hostapd_clients.return_value = {"clients": {}}
    legacy_entry.add_to_hass(hass)
    # A device the legacy entry created before the migration, whose tracker
    # was deleted and whose client is no longer on any network: removing the
    # entry must not delete the device with it.
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=legacy_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
    )
    device_registry.async_update_device(legacy_device.id, name_by_user="My Phone")
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The entry is gone, but the device survived on the hub, untouched.
    assert hass.config_entries.async_entries(DOMAIN) == [hub_entry]
    device = device_registry.async_get(legacy_device.id)
    assert device is not None
    assert device.config_entry_id == hub_entry.entry_id
    assert device.name_by_user == "My Phone"
    # The client is not connected, so no tracker was recreated.
    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE)
        is None
    )


async def test_migration_disabled_entry_becomes_subentry(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a disabled legacy entry becomes an active subentry with a warning."""
    _mock, _ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    disabled_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_HOST_CONFIG_B, title=MOCK_HOST_B
    )
    disabled_entry.disabled_by = ConfigEntryDisabler.USER
    disabled_entry.add_to_hass(hass)
    hub_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [hub_entry]
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_disabled_entry_{disabled_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_disabled_entry"
    assert issue.translation_placeholders == {"host": MOCK_HOST_B}
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_persistent
    assert issue.config_entry_id == hub_entry.entry_id
    subentry = next(
        subentry
        for subentry in hub_entry.subentries.values()
        if subentry.unique_id == MOCK_HOST_B
    )
    assert issue.config_subentry_id == subentry.subentry_id

    # Deleting the subentry clears the warning.
    hass.config_entries.async_remove_subentry(hub_entry, subentry.subentry_id)
    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"migration_disabled_entry_{disabled_entry.entry_id}"
        )
        is None
    )


async def test_migration_disabled_entry_collision_skips_warning(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a colliding disabled entry gets no delete-the-router warning."""
    _mock, _ubus = mock_ubus_by_host
    disabled_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000B",
    )
    disabled_entry.disabled_by = ConfigEntryDisabler.USER
    disabled_entry.add_to_hass(hass)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The colliding disabled entry was removed; its router stays active
    # through the hub's existing subentry, so there is no subentry to
    # delete to restore the old off state.
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert len(mock_config_entry.subentries) == 1
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"migration_disabled_entry_{disabled_entry.entry_id}"
        )
        is None
    )
    # The collision itself is still reported.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_host_collision_{disabled_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_host_collision"
    assert issue.translation_placeholders == {"host": MOCK_HOST}


async def test_migration_idempotent_on_second_setup(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test a second setup of the hub does not re-migrate."""
    _mock, _ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }

    assert await hass.config_entries.async_unload(hub_entry.entry_id)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }


async def test_migration_failure_after_transfer_empties_leftover_entry(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed removal after the transfer leaves a shell entry."""
    _mock, ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    hub_entry.add_to_hass(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_remove",
        side_effect=RuntimeError,
    ):
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    # The transfer completed: the hub owns the router subentry. The
    # leftover entry was emptied before the failed removal, so it is a
    # shell which cannot poll the router again.
    assert MOCK_HOST_B in {sub.unique_id for sub in hub_entry.subentries.values()}
    assert legacy_entry.state is ConfigEntryState.LOADED
    assert legacy_entry.disabled_by is None
    assert legacy_entry.version == 2
    assert legacy_entry.data == {}
    assert legacy_entry.subentries == {}
    # The hub is the only poller: setting up the shell added no second
    # poll of the router.
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_removal_failed_{legacy_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_removal_failed"
    assert issue.translation_placeholders == {"host": MOCK_HOST_B}
    assert issue.config_entry_id == legacy_entry.entry_id
    # The leftover is empty, so the repair can ask for its deletion, in
    # separate numbered steps.
    translations = await async_get_translations(hass, "en", "issues", {DOMAIN})
    description = translations[
        f"component.{DOMAIN}.issues.migration_removal_failed.description"
    ]
    assert "delete" in description.lower()
    assert "\n\n1. " in description
    assert "\n2. " in description

    # Deleting the shell finishes the migration and clears its repair.
    assert await hass.config_entries.async_remove(legacy_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"migration_removal_failed_{legacy_entry.entry_id}"
        )
        is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migration_host_collision(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a duplicate host is removed with a repair issue on collision."""
    _mock, ubus = mock_ubus_by_host
    first = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    duplicate = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000B",
    )
    duplicate.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    first.add_to_hass(hass)
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()

    # The duplicate entry was removed; the hub keeps a single router.
    assert hass.config_entries.async_entries(DOMAIN) == [first]
    assert len(first.subentries) == 1
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_host_collision_{duplicate.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_host_collision"
    # The collision is a one-time notice, not an error: it persists until
    # the user dismisses it after checking the retained router.
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_persistent
    # The tracker was re-parented to the hub before the entry was removed.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == first.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


async def test_migration_unload_failure_keeps_entry(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a legacy entry which cannot be unloaded is left in place."""
    _mock, ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    # A legacy entry which was set up and has not been unloaded yet when
    # the consolidation runs.
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
        state=ConfigEntryState.LOADED,
    )
    legacy_entry.add_to_hass(hass)
    hub_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ubus.async_unload_entry", side_effect=RuntimeError
    ):
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    # The entry which could not be unloaded is left in place with a repair
    # issue; it is set up like any other entry, so its router keeps polling
    # on its own entry, converted to a single-router hub.
    assert legacy_entry in hass.config_entries.async_entries(DOMAIN)
    assert legacy_entry.state is ConfigEntryState.LOADED
    assert legacy_entry.version == 2
    assert legacy_entry.data == {}
    assert {sub.unique_id for sub in legacy_entry.subentries.values()} == {MOCK_HOST_B}
    # Nothing was transferred: the hub has no subentry for the router, the
    # entry is not isolated, and it keeps polling its own router.
    assert legacy_entry.disabled_by is None
    assert MOCK_HOST_B not in {sub.unique_id for sub in hub_entry.subentries.values()}
    assert ubus[MOCK_HOST_B].get_hostapd_clients.call_count == 1
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_failed_{legacy_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_failed"
    # Deleting the entry would drop its tracker references, which a
    # re-added router cannot restore, so the repair must not ask for it.
    translations = await async_get_translations(hass, "en", "issues", {DOMAIN})
    description = translations[
        f"component.{DOMAIN}.issues.migration_failed.description"
    ]
    assert "delete" not in description.lower()
    assert "restart" in description.lower()


async def test_migration_host_collision_keeps_remaining_routers(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a colliding router does not block the transfer of the rest."""
    _mock, _ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        entry_id="00000000000000000000000000A",
        subentries_data=[router_subentry_data(MOCK_HOST_CONFIG_B)],
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
        subentries_data=[
            router_subentry_data(MOCK_HOST_CONFIG_B),
            router_subentry_data(MOCK_HOST_CONFIG_C),
        ],
    )
    hub_entry.add_to_hass(hass)
    legacy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The colliding router kept the hub's copy; the other router was
    # transferred before the entry was removed.
    assert hass.config_entries.async_entries(DOMAIN) == [hub_entry]
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST_B,
        MOCK_HOST_C,
    }
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_host_collision_{legacy_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_host_collision"
    assert issue.translation_placeholders == {"host": MOCK_HOST_B}


async def test_migration_completes_before_entry_startup(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test a consolidated entry can no longer be set up after the hub."""
    _mock, _ubus = mock_ubus_by_host
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
        entry_id="00000000000000000000000000A",
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
        entry_id="00000000000000000000000000B",
    )
    legacy_entry.add_to_hass(hass)
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The migration ran in component setup, before the entry startup
    # snapshot, so the consolidated entry is already gone and the hub is
    # on the new schema version.
    assert hass.config_entries.async_entries(DOMAIN) == [hub_entry]
    assert hub_entry.version == 2
    assert hub_entry.data == {}
    with pytest.raises(UnknownEntry):
        await hass.config_entries.async_setup(legacy_entry.entry_id)


async def test_version_one_entry_converted_at_entry_setup(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test a version-1 entry is converted to the hub schema when set up."""
    _mock, _ubus = mock_ubus_by_host
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=MOCK_HOST,
    )
    legacy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    assert legacy_entry.version == 2
    assert legacy_entry.data == {}
    assert {subentry.unique_id for subentry in legacy_entry.subentries.values()} == {
        MOCK_HOST
    }


async def test_migration_skips_newer_schema_entries(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test an entry on a newer schema is left in place by the migration."""
    _mock, _ubus = mock_ubus_by_host
    # A hub a newer release wrote with a schema this release does not
    # know, which must not be downgraded or consolidated away.
    newer_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        entry_id="00000000000000000000000000A",
        version=3,
        subentries_data=[router_subentry_data(MOCK_HOST_CONFIG_B)],
    )
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_HOST_CONFIG_C,
        title=MOCK_HOST_C,
        entry_id="00000000000000000000000000B",
    )
    newer_entry.add_to_hass(hass)
    legacy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    # The newer entry is untouched, and the legacy entry became its own
    # single-router hub instead of joining it.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert newer_entry.version == 3
    assert newer_entry.data == {}
    assert {sub.unique_id for sub in newer_entry.subentries.values()} == {MOCK_HOST_B}
    assert legacy_entry.version == 2
    assert legacy_entry.data == {}
    assert {sub.unique_id for sub in legacy_entry.subentries.values()} == {MOCK_HOST_C}
