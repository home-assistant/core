"""Unit tests for the device_tracker component of the the OPNsense integration integration.

These tests cover setup, coordinator update handling, restore state behavior,
and device info formatting for the integration's device tracker entities.
"""

from collections.abc import MutableMapping
from datetime import datetime
import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

# import the module under test and package constants
dt_mod = importlib.import_module("homeassistant.components.opnsense.device_tracker")
pkg = importlib.import_module("homeassistant.components.opnsense")


@pytest.mark.asyncio
async def test_async_setup_entry_configured_devices(
    monkeypatch: pytest.MonkeyPatch,
    ph_hass,
    coordinator,
    make_config_entry,
    fake_reg_factory,
) -> None:
    """Setup creates device tracker entities for configured MACs."""
    coordinator.data = {
        "arp_table": [
            {"mac": "aa:bb:cc", "ip": "1.2.3.4", "hostname": "dev", "manufacturer": "m"}
        ]
    }

    entry = make_config_entry(
        data={dt_mod.TRACKED_MACS: [], pkg.CONF_DEVICE_UNIQUE_ID: "dev1"},
        options={
            dt_mod.CONF_DEVICES: ["aa:bb:cc"],
            dt_mod.CONF_DEVICE_TRACKER_ENABLED: True,
        },
        entry_id="eid",
    )
    # attach coordinator into runtime_data under the expected attribute name
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    entry.add_update_listener = lambda f: lambda: None
    entry.async_on_unload = lambda x: None
    hass = ph_hass
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.data = {}

    # use shared fake registry fixture: device does not exist
    fake = fake_reg_factory(device_exists=False)
    monkeypatch.setattr(dt_mod, "async_get_dev_reg", lambda hass: fake, raising=False)

    added = []

    def async_add_entities(ents):
        added.extend(ents)

    await dt_mod.async_setup_entry(hass, entry, async_add_entities)

    assert len(added) == 1
    # the created entity should be the integration's device tracker entity and have a unique_id
    created = added[0]
    assert isinstance(created, dt_mod.OPNsenseScannerEntity)
    # make_config_entry sets the device unique id to a suffix like "mac_<normalized_mac>".
    # slugify should normalize ':' to '_' -> unique_id should end with 'mac_aa_bb_cc'
    uid = getattr(created, "unique_id", None)
    assert uid is not None
    assert uid.startswith("dev1_")
    assert uid.endswith("mac_aa_bb_cc")
    # ensure the normalized MAC components are present in the unique_id
    assert "aa_bb_cc" in uid
    # ensure the MAC is available on the entity (or included in unique_id) and was normalized
    assert created.mac_address == "aa:bb:cc"
    # tracked macs should have been updated on the config entry
    assert hass.config_entries.async_update_entry.called
    # Inspect the update payload to ensure tracked MACs were persisted
    call = hass.config_entries.async_update_entry.call_args
    args = call.args
    kwargs = call.kwargs
    # HA calls async_update_entry(positionally): (entry, data)
    target_entry = args[0]
    updated_data = kwargs.get("data", args[1] if len(args) > 1 else None)

    assert target_entry is entry
    assert updated_data.get(dt_mod.TRACKED_MACS) == ["aa:bb:cc"]


@pytest.mark.asyncio
async def test_async_setup_entry_removes_nonmatching_tracked_macs(
    monkeypatch: pytest.MonkeyPatch,
    ph_hass,
    coordinator,
    make_config_entry,
    fake_reg_factory,
) -> None:
    """Ensure previously-tracked MACs not present in current devices are removed."""
    # coordinator reports only one arp entry
    coordinator.data = {
        "arp_table": [
            {"mac": "aa:bb:cc", "ip": "1.2.3.4", "hostname": "dev", "manufacturer": "m"}
        ]
    }

    # entry previously tracked an extra MAC that is no longer present
    entry = make_config_entry(
        data={
            dt_mod.TRACKED_MACS: ["aa:bb:cc", "ff:ee:dd"],
            pkg.CONF_DEVICE_UNIQUE_ID: "dev1",
        },
        options={
            dt_mod.CONF_DEVICES: ["aa:bb:cc"],
            dt_mod.CONF_DEVICE_TRACKER_ENABLED: True,
        },
        entry_id="eid_remove",
    )
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    entry.add_update_listener = lambda f: lambda: None
    entry.async_on_unload = lambda x: None

    hass = ph_hass
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.data = {}

    fake = fake_reg_factory(device_exists=True, device_id="removed-device-id")
    monkeypatch.setattr(dt_mod, "async_get_dev_reg", lambda hass: fake, raising=False)

    added = []

    def async_add_entities(ents):
        added.extend(ents)

    await dt_mod.async_setup_entry(hass, entry, async_add_entities)

    # ensure an update was persisted and the stale MAC was removed
    assert hass.config_entries.async_update_entry.called
    call = hass.config_entries.async_update_entry.call_args
    args = call.args
    kwargs = call.kwargs
    updated_data = kwargs.get("data", args[1] if len(args) > 1 else None)

    assert updated_data is not None
    # The stale MAC should no longer be present
    assert "ff:ee:dd" not in updated_data.get(dt_mod.TRACKED_MACS, [])
    # The expected remaining MAC should still be present
    assert "aa:bb:cc" in updated_data.get(dt_mod.TRACKED_MACS, [])


@pytest.mark.asyncio
async def test_async_setup_entry_handles_non_list_arp_and_non_string_macs(
    coordinator, make_config_entry
) -> None:
    """Setup should tolerate malformed ARP payloads without creating entities."""
    entry = make_config_entry(
        data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"},
        options={dt_mod.CONF_DEVICE_TRACKER_ENABLED: True},
    )
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    created: list = []
    coordinator.data = {"arp_table": {}}
    await dt_mod.async_setup_entry(MagicMock(), entry, created.extend)
    assert created == []

    coordinator.data = {"arp_table": [{"mac": None}]}
    await dt_mod.async_setup_entry(MagicMock(), entry, created.extend)
    assert created == []


def test_handle_coordinator_update_unavailable(coordinator, make_config_entry) -> None:
    """Coordinator with invalid data should mark entity unavailable."""
    coordinator.data = None
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    assert ent.available is False
    assert ent.async_write_ha_state.called


def test_handle_coordinator_update_entry_present(
    coordinator, make_config_entry
) -> None:
    """Coordinator arp entry populates entity attributes correctly."""
    coordinator.data = {
        "arp_table": [
            {
                "mac": "aa:bb:cc",
                "ip": "1.2.3.4",
                "hostname": "host?",
                "manufacturer": "m",
                "intf_description": "lan0",
                "expires": -1,
                "type": "arp",
            }
        ],
        "update_time": float(int(datetime.now().timestamp())),
    }

    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor="m",
        hostname="host?",
    )
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()

    assert ent.ip_address == "1.2.3.4"
    # hostname should have stripped the trailing '?'
    assert ent.hostname == "host"
    assert ent.is_connected is True
    assert ent.extra_state_attributes.get("expires") == "Never"
    assert ent.extra_state_attributes.get("interface") == "lan0"
    assert ent.extra_state_attributes.get("type") == "arp"


def test_handle_coordinator_update_missing_entry_consider_home(
    coordinator, make_config_entry
) -> None:
    """If missing entry and within consider_home, entity remains connected."""
    coordinator.data = {"arp_table": []}
    entry = make_config_entry(
        data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"},
        options={dt_mod.CONF_DEVICE_TRACKER_CONSIDER_HOME: 3600},
    )
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    # set a recent last known connected time
    ent._last_known_connected_time = datetime.now().astimezone()
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    # elapsed < consider_home so device considered connected
    assert ent.is_connected is True


def test_handle_coordinator_update_uses_last_known_details(
    coordinator, make_config_entry
) -> None:
    """Disconnected entities should surface cached hostname and IP metadata."""
    coordinator.data = {"arp_table": [{"mac": "ff:ee:dd"}]}
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent._last_known_hostname = "cached-host"
    ent._last_known_ip = "10.0.0.5"
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    assert ent.is_connected is False
    assert ent.extra_state_attributes["last_known_hostname"] == "cached-host"
    assert ent.extra_state_attributes["last_known_ip"] == "10.0.0.5"


def test_handle_coordinator_update_tolerates_bad_entry_fields(
    coordinator, make_config_entry
) -> None:
    """Bad hostname/expires values should not crash tracker updates."""
    coordinator.data = {
        "arp_table": [
            {
                "mac": "aa:bb:cc",
                "ip": "1.2.3.4",
                "hostname": 1,
                "expires": "bad",
                "type": "arp",
            }
        ]
    }
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent.async_write_ha_state = MagicMock()
    ent._handle_coordinator_update()
    assert ent.hostname is None
    assert "expires" not in ent.extra_state_attributes


def test_device_tracker_property_getters(coordinator, make_config_entry) -> None:
    """Tracker property getters should expose stored values directly."""
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=True,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname="host",
    )
    assert ent.source_type == dt_mod.SourceType.ROUTER
    assert ent.entity_registry_enabled_default is True


@pytest.mark.asyncio
async def test_restore_last_state_and_device_info(
    monkeypatch: pytest.MonkeyPatch, coordinator, make_config_entry
) -> None:
    """Restoring last state merges saved attributes into the entity."""
    coordinator.data = {"arp_table": []}
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor="mfg",
        hostname="dev",
    )
    ent._attr_extra_state_attributes = {}

    # fake last state with attributes including isoformat time
    last_state = MagicMock()
    last_state.attributes = {
        "last_known_hostname": "oldhost",
        "last_known_ip": "9.9.9.9",
        "interface": "lan0",
        "expires": 10,
        "type": "arp",
        "last_known_connected_time": datetime.now().isoformat(),
    }
    ent.async_get_last_state = AsyncMock(return_value=last_state)

    await ent._restore_last_state()
    # restored attributes should be present
    assert ent._last_known_hostname == "oldhost"
    assert ent._last_known_ip == "9.9.9.9"
    assert ent.extra_state_attributes.get("interface") == "lan0"
    assert "last_known_connected_time" in ent.extra_state_attributes

    # device_info should include the mac connection and via_device tuple
    devinfo = ent.device_info
    # support both DeviceInfo object and dict-shaped DeviceInfo used in tests
    if isinstance(devinfo, MutableMapping):
        connections = devinfo.get("connections", [])
        via = devinfo.get("via_device")
    else:
        connections = getattr(devinfo, "connections", [])
        via = getattr(devinfo, "via_device", None)

    assert any(t[1] == "aa:bb:cc" for t in connections)
    assert via[0] == dt_mod.DOMAIN
    assert via[1] == entry.data[pkg.CONF_DEVICE_UNIQUE_ID]


@pytest.mark.asyncio
async def test_restore_last_state_guard_branches(
    coordinator, make_config_entry
) -> None:
    """Restore should no-op without state and accept datetime values directly."""
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )

    ent.async_get_last_state = AsyncMock(return_value=None)
    await ent._restore_last_state()

    now = datetime.now().astimezone()
    last_state = MagicMock()
    last_state.attributes = {"last_known_connected_time": now}
    ent.async_get_last_state = AsyncMock(return_value=last_state)
    await ent._restore_last_state()
    assert ent.extra_state_attributes["last_known_connected_time"] == now


@pytest.mark.asyncio
async def test_async_added_to_hass_calls_restore(
    monkeypatch: pytest.MonkeyPatch, coordinator, make_config_entry
) -> None:
    """Entity.async_added_to_hass should call state restoration."""
    coordinator.data = {"arp_table": []}
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )

    # patch the restore method and the parent async_added_to_hass to avoid side effects
    ent._restore_last_state = AsyncMock()
    # patch the base class async_added_to_hass (no-op)
    base_mod = importlib.import_module("homeassistant.components.opnsense.entity")
    monkeypatch.setattr(base_mod.OPNsenseBaseEntity, "async_added_to_hass", AsyncMock())

    await ent.async_added_to_hass()
    assert ent._restore_last_state.called


@pytest.mark.asyncio
async def test_async_setup_entry_state_not_mapping(
    ph_hass, coordinator, make_config_entry
) -> None:
    """Setup exits early when coordinator state is not a mapping."""
    # coordinator.data is not a mapping -> async_setup_entry should return early and not add entities
    coordinator.data = "not-a-mapping"
    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    added = []

    hass = ph_hass
    hass.data = {}
    hass.config_entries.async_update_entry = MagicMock()

    await dt_mod.async_setup_entry(hass, entry, added.extend)
    assert len(added) == 0
    assert not hass.config_entries.async_update_entry.called


@pytest.mark.asyncio
async def test_async_setup_entry_removes_previous_mac(
    monkeypatch: pytest.MonkeyPatch,
    ph_hass,
    coordinator,
    make_config_entry,
    fake_reg_factory,
) -> None:
    """Setup removes previously tracked MAC addresses when reconfiguring."""
    # previous tracked macs include an old mac that should be removed via device registry
    coordinator.data = {"arp_table": []}
    entry = make_config_entry(
        data={dt_mod.TRACKED_MACS: ["old:mac:1"], pkg.CONF_DEVICE_UNIQUE_ID: "dev1"},
        entry_id="e_rm",
    )
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    hass = ph_hass
    hass.data = {}

    # use shared fake registry fixture: simulate device present and removal
    fake = fake_reg_factory(device_exists=True, device_id="dev_to_remove")
    monkeypatch.setattr(dt_mod.dr, "async_get", lambda hass: fake, raising=False)

    hass.config_entries.async_update_entry = MagicMock()

    await dt_mod.async_setup_entry(hass, entry, lambda x: None)
    assert fake.removed is True
    assert hass.config_entries.async_update_entry.called


def test_handle_coordinator_update_expires_positive(
    coordinator, make_config_entry
) -> None:
    """Expired ARP entries set entity to disconnected and update attributes."""
    coordinator.data = {
        "arp_table": [
            {
                "mac": "aa:bb:cc",
                "ip": "1.2.3.4",
                "hostname": "hn",
                "intf_description": "lan",
                "expires": 30,
            }
        ],
        "update_time": float(int(datetime.now().timestamp())),
    }

    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    assert isinstance(ent.extra_state_attributes.get("expires"), datetime)


def test_handle_coordinator_update_ip_typeerror(coordinator, make_config_entry) -> None:
    """Handle TypeError when entry IP is None and avoid crashing."""
    coordinator.data = {"arp_table": [{"mac": "aa:bb:cc", "ip": None}]}

    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    # no exception and ip_address is None
    assert ent.ip_address is None


def test_handle_coordinator_update_expired_preserve_last_known_ip(
    coordinator, make_config_entry
) -> None:
    """Expired entries preserve last_known_ip when no IP present."""
    # expired entry should set is_connected False and preserve last_known_ip
    # no ip in entry triggers branch where last_known_ip is preserved
    coordinator.data = {"arp_table": [{"mac": "aa:bb:cc", "expired": True}]}

    entry = make_config_entry(data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"})
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)

    ent = dt_mod.OPNsenseScannerEntity(
        config_entry=entry,
        coordinator=coordinator,
        enabled_default=False,
        mac="aa:bb:cc",
        mac_vendor=None,
        hostname=None,
    )
    ent._last_known_ip = "1.2.3.4"
    ent.async_write_ha_state = MagicMock()

    ent._handle_coordinator_update()
    assert ent.is_connected is False
    assert ent.extra_state_attributes.get("last_known_ip") == "1.2.3.4"


@pytest.mark.asyncio
async def test_async_setup_entry_from_arp_entries(
    monkeypatch: pytest.MonkeyPatch,
    ph_hass,
    coordinator,
    make_config_entry,
) -> None:
    """Setup from ARP entries creates device trackers for present ARP rows."""
    # when CONF_DEVICES not set but device tracker enabled, create entity per arp entry
    coordinator.data = {"arp_table": [{"mac": "m1"}, {"mac": "m2", "hostname": "h2"}]}
    entry = make_config_entry(
        data={pkg.CONF_DEVICE_UNIQUE_ID: "dev1"},
        options={dt_mod.CONF_DEVICE_TRACKER_ENABLED: True},
        entry_id="eid2",
    )
    setattr(entry.runtime_data, dt_mod.DEVICE_TRACKER_COORDINATOR, coordinator)
    hass = ph_hass
    hass.data = {}
    hass.config_entries.async_update_entry = MagicMock()

    added = []

    await dt_mod.async_setup_entry(hass, entry, added.extend)
    assert len(added) == 2
    assert all(isinstance(e, dt_mod.OPNsenseScannerEntity) for e in added)
    assert {e.unique_id for e in added} == {"dev1_mac_m1", "dev1_mac_m2"}
