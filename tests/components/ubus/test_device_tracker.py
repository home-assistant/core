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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import MAC_GUEST, MAC_LAPTOP, MAC_PHONE, MOCK_CONFIG, MOCK_HOST


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


async def test_setup_scanner_imports_yaml(
    hass: HomeAssistant, mock_ubus: MagicMock
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
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == MOCK_CONFIG


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
