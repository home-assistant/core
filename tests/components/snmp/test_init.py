"""SNMP tests."""

import binascii
from datetime import timedelta
from unittest.mock import Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant.components import snmp
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import (
    CONF_BASEOID,
    CONF_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ARP_TABLE_MAC_OID, mock_entry

from tests.common import MockConfigEntry

MAC = "00:11:22:33:44:55"

# ipNetToMediaPhysAddress, the MAC column of the ARP table
ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)


async def _async_mock_walk_with_mac(*args, **kwargs):
    """Yield a single MAC address from the ARP table."""
    oid = Mock()
    oid.asTuple.return_value = (*ARP_MAC_OID, 1, 192, 168, 1, 1)
    yield None, None, None, [(oid, OctetString(binascii.unhexlify("001122334455")))]


def _async_mac_entity_id(hass: HomeAssistant) -> str | None:
    """Return the registry entity id of the MAC the tests walk."""
    return er.async_get(hass).async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)


async def _async_mock_walk(*args, **kwargs):
    """Return an empty walk."""
    return
    yield  # pylint: disable=unreachable


async def test_async_get_snmp_engine(hass: HomeAssistant) -> None:
    """Test async_get_snmp_engine."""
    engine = await snmp.async_get_snmp_engine(hass)
    assert isinstance(engine, SnmpEngine)
    engine2 = await snmp.async_get_snmp_engine(hass)
    assert engine is engine2
    with patch.object(LCD, "unconfigure") as mock_unconfigure:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    assert mock_unconfigure.called


async def test_async_setup_entry_custom_port(
    hass: HomeAssistant, mock_udp_transport: Mock
) -> None:
    """Test async_setup_entry with a custom port."""
    entry = mock_entry(host="1.2.3.4")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_udp_transport.assert_called_once()
    args, _ = mock_udp_transport.call_args
    assert args[0] == ("1.2.3.4", 161)


async def test_async_setup_entry_custom_port_used(hass: HomeAssistant) -> None:
    """Test that the configured port is used."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            CONF_PORT: 1161,
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=_async_mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value=Mock(),
        ) as mock_create,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    args, _ = mock_create.call_args
    assert args[0] == ("1.2.3.4", 1161)


async def test_async_setup_entry_v3_no_keys(hass: HomeAssistant) -> None:
    """Test async_setup_entry with SNMP v3 and no auth/priv keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="1.2.3.4",
        data={
            "host": "1.2.3.4",
            "version": "3",
            "username": "test-user",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_async_setup_entry_ipv6_fallback(hass: HomeAssistant) -> None:
    """Test async_setup_entry with IPv6 fallback."""
    entry = mock_entry(host="1.2.3.4")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            return_value=Mock(),
        ) as mock_create6,
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=_async_mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_create6.assert_called_once()


async def test_async_setup_entry_fail_all(hass: HomeAssistant) -> None:
    """Test async_setup_entry failing both IPv4 and IPv6."""
    entry = mock_entry(host="1.2.3.4")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            side_effect=PySnmpError,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_unexpected_error(hass: HomeAssistant) -> None:
    """Test async_setup_entry with an unexpected error."""
    entry = mock_entry(host="1.2.3.4")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.util.UdpTransportTarget.create",
        side_effect=RuntimeError("Something unexpected"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_without_subentries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a device without capabilities is set up."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not entry.runtime_data.coordinators

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == entry.title


async def test_device_name_from_sys_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the host device is named after the sysName of the device."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=_async_mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.client.get_cmd",
            return_value=(None, None, None, [("oid1", "router01")]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == "router01"
    assert device.manufacturer is None
    assert device.model is None
    assert device.sw_version is None


@pytest.mark.parametrize(
    "get_cmd_result",
    [
        pytest.param(PySnmpError("Connection timed out"), id="exception"),
        pytest.param(("some error indication", None, None, []), id="errindication"),
        pytest.param((None, None, None, []), id="no_data"),
    ],
)
async def test_device_name_falls_back_to_entry_title(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    get_cmd_result: PySnmpError | tuple,
) -> None:
    """Test that the host device falls back to the title when sysName is unknown."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=_async_mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.client.get_cmd",
            side_effect=get_cmd_result
            if isinstance(get_cmd_result, Exception)
            else None,
            return_value=None
            if isinstance(get_cmd_result, Exception)
            else get_cmd_result,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == entry.title


async def test_walk_error_makes_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that a PySnmpError during walk makes the entry retry."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    async def mock_walk_error(*args, **kwargs):
        raise PySnmpError("Network unreachable")
        yield  # pylint: disable=unreachable

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk_error,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_walk_errstatus(hass: HomeAssistant) -> None:
    """Test that errstatus during walk makes the entry retry."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    mock_err_status = Mock()
    mock_err_status.prettyPrint.return_value = "noSuchName"

    async def mock_walk(*args, **kwargs):
        yield None, mock_err_status, 1, [("oid", "val")]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_walk_auth_error(hass: HomeAssistant) -> None:
    """Test that WrongValueError during walk triggers reauth."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=WrongValueError,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntry.async_start_reauth_if_available"
        ) as reauth,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert reauth.called


async def test_auth_data_auth_error(hass: HomeAssistant) -> None:
    """Test that invalid v3 credentials trigger reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="1.2.3.4",
        data={
            "host": "1.2.3.4",
            "version": "3",
            "username": "test-user",
            "auth_key": "auth-key",
            "auth_protocol": "hmac-sha",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.client.create_auth_data",
            side_effect=WrongValueError,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntry.async_start_reauth_if_available"
        ) as reauth,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert reauth.called


@pytest.mark.parametrize(
    "baseoid",
    [ARP_TABLE_MAC_OID, None],
    ids=["with_subentry", "without_subentry"],
)
async def test_async_setup_entry_unload(
    hass: HomeAssistant, baseoid: str | None
) -> None:
    """Test that an entry unloads with and without a device tracker subentry."""
    entry = mock_entry(baseoid=baseoid)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_subentry_added_after_setup(hass: HomeAssistant) -> None:
    """Test that a device tracker added after setup loads its entity."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk_with_mac,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not entry.runtime_data.coordinators
        assert _async_mac_entity_id(hass) is None

        subentry = ConfigSubentry(
            data={CONF_BASEOID: ARP_TABLE_MAC_OID},
            subentry_type=SUBENTRY_TYPE_DEVICE_TRACKER,
            title="Device tracker",
            unique_id=SUBENTRY_TYPE_DEVICE_TRACKER,
        )
        assert hass.config_entries.async_add_subentry(entry, subentry)
        await hass.async_block_till_done()

    assert set(entry.runtime_data.coordinators) == {subentry.subentry_id}
    assert set(entry.runtime_data.coordinators[subentry.subentry_id].data) == {MAC}
    assert _async_mac_entity_id(hass) is not None


async def test_subentry_removed_after_setup(hass: HomeAssistant) -> None:
    """Test that removing the device tracker removes its entity and coordinator."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk_with_mac,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert _async_mac_entity_id(hass) is not None

        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

    assert not entry.runtime_data.coordinators
    assert _async_mac_entity_id(hass) is None


async def test_subentry_reconfigure_reloads_coordinator(hass: HomeAssistant) -> None:
    """Test that reconfiguring the device tracker reloads its coordinator."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk_with_mac,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.coordinators[subentry_id].update_interval == (
            DEFAULT_SCAN_INTERVAL
        )

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_BASEOID: ARP_TABLE_MAC_OID,
                CONF_INTERVAL_SECONDS: 60,
            },
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_INTERVAL_SECONDS] == 60
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinators[subentry_id].update_interval == timedelta(
        seconds=60
    )
    assert _async_mac_entity_id(hass) is not None
