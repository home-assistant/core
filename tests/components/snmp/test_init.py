"""SNMP tests."""

import asyncio
import binascii
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest
from pytest_homeassistant.common import async_capture_events, async_fire_time_changed

from homeassistant.components import snmp
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import (
    CONF_BASEOID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.components.snmp.coordinator import MAX_CONSECUTIVE_FAILURES
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState, ConfigSubentry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ARP_TABLE_MAC_OID, mock_entry

pytestmark = pytest.mark.usefixtures("mock_udp_transport")

MAC = "00:11:22:33:44:55"
MAC_BYTES = "001122334455"

# ipNetToMediaPhysAddress, the MAC column of the ARP table
ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)

# dot1dTpFdbAddress, the MAC column of the bridge forwarding table
BRIDGE_MAC_OID = "1.3.6.1.2.1.17.4.3.1.1"


async def _async_mock_walk_with_mac(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
    """Yield a single MAC address from the ARP table."""
    oid = Mock()
    oid.asTuple.return_value = (*ARP_MAC_OID, 1, 192, 168, 1, 1)
    yield None, None, None, [(oid, OctetString(binascii.unhexlify("001122334455")))]


def _async_mac_entity_id(hass: HomeAssistant, subentry_id: str) -> str | None:
    """Return the registry entity id of the MAC the tests walk."""
    return er.async_get(hass).async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, f"{subentry_id}_{MAC}"
    )


async def _async_mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
    """Return an empty walk."""
    return
    yield  # pylint: disable=unreachable


def _async_reauth_flow(hass: HomeAssistant) -> bool:
    """Return True when a reauthentication flow is in progress."""
    return any(
        flow["context"].get("source") == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def _async_advance_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance a single poll."""
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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
    entry = mock_entry(host="1.2.3.4", version="2c", port=1161)
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
    entry = mock_entry(host="1.2.3.4", version="3", username="test-user", baseoid=None)
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
    """Test that an entry without capabilities sets up without a device."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not entry.runtime_data.coordinators
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)


async def test_walk_error_makes_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that a PySnmpError during walk makes the entry retry."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    async def mock_walk_error(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
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

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, mock_err_status, 1, [("oid", "val")]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_walk_value_error_does_not_reauthenticate(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_walk: Mock
) -> None:
    """Test that an unconvertible value is retried instead of triggering reauth."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_walk.side_effect = WrongValueError
    await _async_advance_poll(hass, freezer)

    assert not _async_reauth_flow(hass)


async def test_walk_value_error_makes_coordinator_fail(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_walk: Mock
) -> None:
    """Test that repeated unconvertible values fail the coordinator after a retry."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(entry.subentries))
    coordinator = entry.runtime_data.coordinators[subentry_id]
    mock_walk.side_effect = WrongValueError

    await _async_advance_poll(hass, freezer)
    assert coordinator.last_update_success

    for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
        await _async_advance_poll(hass, freezer)

    assert not coordinator.last_update_success


@pytest.mark.parametrize(
    "errindication",
    [
        pytest.param(errind.wrongDigest, id="wrong_digest"),
        pytest.param(errind.unknownUserName, id="unknown_user_name"),
        pytest.param(errind.authenticationFailure, id="authentication_failure"),
    ],
)
async def test_walk_auth_indication_triggers_reauth(
    hass: HomeAssistant,
    errindication: errind.ErrorIndication,
    freezer: FrozenDateTimeFactory,
    mock_walk: Mock,
) -> None:
    """Test that an authentication indication during a poll triggers reauth."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def mock_walk_auth(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield errindication, None, None, []

    mock_walk.side_effect = mock_walk_auth
    await _async_advance_poll(hass, freezer)

    assert _async_reauth_flow(hass)


async def test_auth_data_auth_error(hass: HomeAssistant) -> None:
    """Test that credentials which cannot be built fail the setup."""
    entry = mock_entry(
        host="1.2.3.4",
        version="3",
        username="test-user",
        auth_key="auth-key",
        auth_protocol="hmac-sha",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snmp.util.UsmUserData",
        side_effect=WrongValueError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


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


async def test_subentry_added_after_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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
        assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)

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
    assert _async_mac_entity_id(hass, subentry.subentry_id) is not None


async def test_subentry_added_during_setup(hass: HomeAssistant) -> None:
    """Test that a tracker added while the entry starts up is not lost."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()

    async def blocking_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Block the poll until the test has added the subentry."""
        refresh_started.set()
        await release_refresh.wait()
        async for row in _async_mock_walk_with_mac(*args, **kwargs):
            yield row

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=blocking_walk,
    ):
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(entry.entry_id)
        )
        await refresh_started.wait()

        second = ConfigSubentry(
            data={CONF_BASEOID: BRIDGE_MAC_OID},
            subentry_type=SUBENTRY_TYPE_DEVICE_TRACKER,
            title=BRIDGE_MAC_OID,
            unique_id=BRIDGE_MAC_OID,
        )
        assert hass.config_entries.async_add_subentry(entry, second)

        release_refresh.set()
        assert await setup_task
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.coordinators) == {
        next(iter(entry.subentries)),
        second.subentry_id,
    }
    assert _async_mac_entity_id(hass, second.subentry_id) is not None


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
        assert _async_mac_entity_id(hass, subentry_id) is not None

        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

    assert not entry.runtime_data.coordinators
    assert _async_mac_entity_id(hass, subentry_id) is None


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
        previous_coordinator = entry.runtime_data.coordinators[subentry_id]

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_BASEOID: BRIDGE_MAC_OID},
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinators[subentry_id] is not previous_coordinator


@pytest.mark.parametrize(
    "survives",
    [
        pytest.param(False, id="mac_only_in_previous_table"),
        pytest.param(True, id="mac_in_both_tables"),
    ],
)
async def test_subentry_reconfigure_switches_table(
    hass: HomeAssistant, survives: bool
) -> None:
    """Test which trackers survive a change to a table that holds other MACs."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    table = {"macs": [MAC_BYTES]}

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Yield the MACs of the table which is currently being walked."""
        oid = Mock()
        oid.asTuple.return_value = (*ARP_MAC_OID, 1, 192, 168, 1, 1)
        for mac in table["macs"]:
            yield None, None, None, [(oid, OctetString(binascii.unhexlify(mac)))]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = _async_mac_entity_id(hass, subentry_id)
        assert entity_id is not None

        table["macs"] = [MAC_BYTES] if survives else []
        events = async_capture_events(hass, er.EVENT_ENTITY_REGISTRY_UPDATED)
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_BASEOID: BRIDGE_MAC_OID},
        )
        await hass.async_block_till_done()

    removed = {
        event.data["entity_id"] for event in events if event.data["action"] == "remove"
    }
    assert result["reason"] == "reconfigure_successful"
    assert (entity_id in removed) is not survives
    # A surviving tracker keeps its registry entry, and with it the person
    # associations which are dropped when an entity is removed.
    assert (_async_mac_entity_id(hass, subentry_id) == entity_id) is survives


async def test_subentry_reconfigure_to_tracked_table_keeps_entities(
    hass: HomeAssistant,
) -> None:
    """Test that aborting a reconfigure does not remove the current entities."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    second = ConfigSubentry(
        data={CONF_BASEOID: BRIDGE_MAC_OID},
        subentry_type=SUBENTRY_TYPE_DEVICE_TRACKER,
        title=BRIDGE_MAC_OID,
        unique_id=BRIDGE_MAC_OID,
    )
    assert hass.config_entries.async_add_subentry(entry, second)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=_async_mock_walk_with_mac,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert _async_mac_entity_id(hass, subentry_id) is not None

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_BASEOID: BRIDGE_MAC_OID},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert _async_mac_entity_id(hass, subentry_id) is not None


async def test_subentry_reconfigure_keeps_other_table_entities(
    hass: HomeAssistant,
) -> None:
    """Test that switching one table leaves the trackers of another table alone."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    second = ConfigSubentry(
        data={CONF_BASEOID: BRIDGE_MAC_OID},
        subentry_type=SUBENTRY_TYPE_DEVICE_TRACKER,
        title=BRIDGE_MAC_OID,
        unique_id=BRIDGE_MAC_OID,
    )
    assert hass.config_entries.async_add_subentry(entry, second)
    table = {"macs": [MAC_BYTES]}

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Yield the MACs of the table which is currently being walked."""
        oid = Mock()
        oid.asTuple.return_value = (*ARP_MAC_OID, 1, 192, 168, 1, 1)
        for mac in table["macs"]:
            yield None, None, None, [(oid, OctetString(binascii.unhexlify(mac)))]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = _async_mac_entity_id(hass, subentry_id)
        other_entity_id = _async_mac_entity_id(hass, second.subentry_id)
        assert entity_id is not None
        assert other_entity_id is not None

        # The new table is empty, so the switched tracker loses its entity while
        # the tracker of the other table keeps its own.
        table["macs"] = []
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.3"},
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert _async_mac_entity_id(hass, subentry_id) is None
    assert _async_mac_entity_id(hass, second.subentry_id) == other_entity_id
