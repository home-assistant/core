"""Tests for the OpenWrt (ubus) device tracker."""

from datetime import timedelta
import threading
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import DOMAIN
from homeassistant.components.ubus.coordinator import LEASE_REREAD_INTERVAL
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntries,
    ConfigEntryDisabler,
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
    MOCK_HOST_CONFIG_B,
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
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    expected_names: dict[str, str],
) -> None:
    """Test that authorized clients become entities and names resolve per backend."""
    hub_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, hub_entry.entry_id)

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
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the source attribute identifies the router the device is connected to."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
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
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped client stays home while its last stamp is recent.

    The dropping router keeps polling after the client drops, but its
    polls do not extend the client's last stamp.
    """
    mock_ubus.return_value.get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    mock_ubus.return_value.get_hostapd_clients.return_value = {"clients": {}}
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
        await hass.async_block_till_done()
    finally:
        release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The in-flight refresh finishes after the removal; its results are
    # ignored, so without a fresh stamp the tracker is unavailable.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_failed_unload_keeps_client_reported(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a failed unload leaves the router reporting its clients."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
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
        assert not await hass.config_entries.async_unload(hub_entry.entry_id)
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
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed tracker is recreated with its original entity ID."""
    _mock, ubus = mock_ubus_by_host
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
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
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    method: str,
) -> None:
    """Test an empty lease read names only new devices after their MAC."""
    getattr(mock_ubus.return_value, method).return_value = None
    hub_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
        name="my-phone",
    )

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), hub_entry.entry_id
    )
    laptop = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_LAPTOP), hub_entry.entry_id
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
    hub_entry: MockConfigEntry,
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
    hub_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert (hass.states.get(entity_id) is not None) is enabled
    phone = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), hub_entry.entry_id
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
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trackers which are disabled by default are only created once."""
    hub_entry.add_to_hass(hass)
    with patch.object(
        UbusScannerEntity,
        "__init__",
        autospec=True,
        side_effect=UbusScannerEntity.__init__,
    ) as mock_init:
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()
        for _ in range(3):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_init.call_count == 2
    entries = er.async_entries_for_config_entry(entity_registry, hub_entry.entry_id)
    assert {e.disabled_by for e in entries} == {er.RegistryEntryDisabler.INTEGRATION}


async def test_other_entry_device_removal_keeps_tracking(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing another entry's device for a tracked MAC is ignored."""
    hub_entry.add_to_hass(hass)
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
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()
        device_registry.async_remove_device(other_device.id)
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_init.call_count == 2


async def test_lease_reread_throttled_for_clients_without_hostname(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
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
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
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
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lease reread without a known client keeps its hostname."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
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
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), hub_entry.entry_id
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
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == legacy_entry.entry_id
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), legacy_entry.entry_id
    )
    assert device is not None

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
    assert device_registry.async_get(device.id) is not None
    assert device_registry.async_get(device.id).config_entry_id == hub_entry.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_migration_merges_device_into_hubs_device(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a legacy device is merged into the hub's device for the client."""
    _mock, ubus = mock_ubus_by_host
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
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    legacy_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), legacy_entry.entry_id
    )
    assert legacy_device is not None
    hub_entry.add_to_hass(hass)
    # The hub already holds a device for the client.
    hub_device = device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_PHONE)},
        name="Hub Phone",
    )

    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The legacy device was merged into the hub's device.
    assert device_registry.async_get(legacy_device.id) is None
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == hub_device.id
    assert device_registry.async_get(hub_device.id).name == "Hub Phone"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


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
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
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


async def test_migration_failure_leaves_entry_and_reports(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an un-migratable entry is left in place with a repair issue."""
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
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    hub_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ubus._async_reparent", side_effect=RuntimeError
    ):
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    # The legacy entry was left in place with a repair issue.
    assert legacy_entry in hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"migration_failed_{legacy_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "migration_failed"
    assert issue.translation_placeholders == {"host": MOCK_HOST_B}


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
    assert await hass.config_entries.async_setup(duplicate.entry_id)
    await hass.async_block_till_done()
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
    # The tracker was re-parented to the hub before the entry was removed.
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).config_entry_id == first.entry_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
