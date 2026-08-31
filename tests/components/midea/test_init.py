"""Tests for midea __init__.py."""

from unittest.mock import patch

from midealocal.const import DeviceType, ProtocolVersion

from homeassistant.components.midea.const import CONF_KEY, CONF_SN, CONF_SUBTYPE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import DummyDevice
from .const import TEST_DEVICE_ID, TEST_IP_ADDRESS, TEST_MAC_ADDRESS, TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry

_ENTRY_DATA = {
    CONF_DEVICE_ID: TEST_DEVICE_ID,
    CONF_NAME: "m",
    CONF_TYPE: DeviceType.AC,
    CONF_IP_ADDRESS: "1.1.1.1",
    CONF_PORT: 6444,
    CONF_MODEL: "m",
    CONF_PROTOCOL: ProtocolVersion.V2,
    CONF_TOKEN: "",
    CONF_KEY: "",
    CONF_SUBTYPE: 0,
}


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the midea domain can be set up without any config entries."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry unloads platforms and closes the device."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=2)
    entry.add_to_hass(hass)
    device = DummyDevice(DeviceType.AC)
    with patch(
        "homeassistant.components.midea.device_selector",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert device.daemon is True
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert ("close",) in device.calls


async def test_async_setup_entry_paths(hass: HomeAssistant) -> None:
    """Test async_setup_entry for success and no-device return."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea.device_selector",
        return_value=DummyDevice(DeviceType.AC),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={**_ENTRY_DATA, CONF_DEVICE_ID: TEST_DEVICE_ID + 1},
        minor_version=2,
    )
    entry2.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea.device_selector",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry2.entry_id)
    assert entry2.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready_on_connect_failure(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when connect returns False.

    The real device.connect() already catches SocketException/AuthException
    internally and reports failure by returning False; it never raises them.
    It can also leave the socket open in that case (e.g. when authentication
    fails), so the socket must be closed explicitly to avoid a ResourceWarning.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=2)
    entry.add_to_hass(hass)
    device = DummyDevice(DeviceType.AC)
    with (
        patch(
            "homeassistant.components.midea.device_selector",
            return_value=device,
        ),
        patch.object(device, "connect", return_value=False),
        patch("homeassistant.components.midea.discover", return_value={}),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert ("close_socket",) in device.calls
    assert entry.data[CONF_IP_ADDRESS] == _ENTRY_DATA[CONF_IP_ADDRESS]


async def test_setup_entry_recovers_ip_on_connect_failure(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry loads successfully after discovering a moved device.

    When the stored IP no longer answers, a device with the same device_id
    found at a different address by the discovery broadcast should update
    the config entry and connect there, finishing setup normally.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    stale_device = DummyDevice(DeviceType.AC)
    recovered_device = DummyDevice(DeviceType.AC)

    with (
        patch(
            "homeassistant.components.midea.device_selector",
            side_effect=[stale_device, recovered_device],
        ),
        patch.object(stale_device, "connect", return_value=False),
        patch(
            "homeassistant.components.midea.discover",
            return_value={TEST_DEVICE_ID: {CONF_IP_ADDRESS: "2.2.2.2"}},
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_IP_ADDRESS] == "2.2.2.2"
    assert recovered_device.daemon is True
    assert ("open",) in recovered_device.calls


async def test_setup_entry_no_recovery_when_device_not_discovered(
    hass: HomeAssistant,
) -> None:
    """Test the stored IP is left untouched when discovery finds no match."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    device = DummyDevice(DeviceType.AC)
    with (
        patch(
            "homeassistant.components.midea.device_selector",
            return_value=device,
        ),
        patch.object(device, "connect", return_value=False),
        patch(
            "homeassistant.components.midea.discover",
            return_value={TEST_DEVICE_ID + 1: {CONF_IP_ADDRESS: "2.2.2.2"}},
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.data[CONF_IP_ADDRESS] == _ENTRY_DATA[CONF_IP_ADDRESS]


async def test_migrate_entry_backfills_mac_and_serial_number(
    hass: HomeAssistant,
) -> None:
    """Test migration to minor_version 2 backfills mac and serial number."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=1)
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.midea.discover",
            return_value={
                TEST_DEVICE_ID: {
                    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                    CONF_MAC: TEST_MAC_ADDRESS,
                    CONF_SN: TEST_SERIAL_NUMBER,
                }
            },
        ),
        patch(
            "homeassistant.components.midea.device_selector",
            return_value=DummyDevice(DeviceType.AC),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data[CONF_MAC] == TEST_MAC_ADDRESS
    assert entry.data[CONF_SN] == TEST_SERIAL_NUMBER


async def test_migrate_entry_drops_empty_mac_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration removes a leftover empty network-mac connection."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=1)
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(TEST_DEVICE_ID))},
        connections={
            (dr.CONNECTION_NETWORK_MAC, "None"),
            (dr.CONNECTION_NETWORK_MAC, TEST_MAC_ADDRESS),
        },
    )

    with (
        patch(
            "homeassistant.components.midea.discover",
            return_value={
                TEST_DEVICE_ID: {
                    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                    CONF_MAC: TEST_MAC_ADDRESS,
                    CONF_SN: TEST_SERIAL_NUMBER,
                }
            },
        ),
        patch(
            "homeassistant.components.midea.device_selector",
            return_value=DummyDevice(DeviceType.AC),
        ) as device_selector,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        device_selector.assert_called_once_with(
            entry.data[CONF_NAME],
            entry.data[CONF_DEVICE_ID],
            entry.data[CONF_TYPE],
            TEST_IP_ADDRESS,
            entry.data[CONF_PORT],
            entry.data[CONF_TOKEN],
            entry.data[CONF_KEY],
            ProtocolVersion(entry.data[CONF_PROTOCOL]),
            entry.data[CONF_MODEL],
            entry.data[CONF_SUBTYPE],
            "",
            entry.data.get(CONF_MAC, None),
            entry.data.get(CONF_SN, None),
        )

    assert entry.state is ConfigEntryState.LOADED
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(TEST_DEVICE_ID)), entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC_ADDRESS)}


async def test_migrate_entry_without_discovery_result(hass: HomeAssistant) -> None:
    """Test migration still completes when discovery finds nothing."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA, minor_version=1)
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.midea.discover", return_value={}),
        patch(
            "homeassistant.components.midea.device_selector",
            return_value=DummyDevice(DeviceType.AC),
        ) as device_selector,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        device_selector.assert_called_once_with(
            entry.data[CONF_NAME],
            entry.data[CONF_DEVICE_ID],
            entry.data[CONF_TYPE],
            TEST_IP_ADDRESS,
            entry.data[CONF_PORT],
            entry.data[CONF_TOKEN],
            entry.data[CONF_KEY],
            ProtocolVersion(entry.data[CONF_PROTOCOL]),
            entry.data[CONF_MODEL],
            entry.data[CONF_SUBTYPE],
            "",
            None,
            None,
        )

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert CONF_MAC not in entry.data
    assert CONF_SN not in entry.data
