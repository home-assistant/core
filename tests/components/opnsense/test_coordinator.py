"""Unit tests for homeassistant.components.opnsense.coordinator.

These tests exercise the coordinator logic paths: initialization errors,
category building, state fetching, device ID mismatch handling, speed
calculations, and update flow.
"""

from collections.abc import MutableMapping
from datetime import timedelta
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.opnsense import coordinator as coordinator_module
from homeassistant.components.opnsense.const import (
    ATTR_UNBOUND_BLOCKLIST,
    CONF_DEVICE_UNIQUE_ID,
    CONF_SYNC_CARP,
    CONF_SYNC_CERTIFICATES,
    CONF_SYNC_DHCP_LEASES,
    CONF_SYNC_FIREWALL_AND_NAT,
    CONF_SYNC_FIRMWARE_UPDATES,
    CONF_SYNC_GATEWAYS,
    CONF_SYNC_INTERFACES,
    CONF_SYNC_NOTICES,
    CONF_SYNC_SERVICES,
    CONF_SYNC_SPEEDTEST,
    CONF_SYNC_TELEMETRY,
    CONF_SYNC_UNBOUND,
    CONF_SYNC_VNSTAT,
    CONF_SYNC_VPN,
)
from homeassistant.components.opnsense.coordinator import OPNsenseDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.asyncio
async def test_init_requires_config_entry(fake_client) -> None:
    """Ensure coordinator initialization requires a config entry."""
    with pytest.raises(ValueError):
        OPNsenseDataUpdateCoordinator(
            hass=MagicMock(),
            client=fake_client()(),
            name="test",
            update_interval=timedelta(seconds=1),
            device_unique_id="id",
            config_entry=None,
        )


@pytest.mark.asyncio
async def test_build_categories_respects_flags(make_config_entry, fake_client) -> None:
    """Categories builder respects configuration sync flags."""
    entry = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "id", CONF_SYNC_INTERFACES: True, CONF_SYNC_VPN: True}
    )
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )
    # categories built on init
    keys = [c["state_key"] for c in coord._categories]
    assert "interfaces" in keys
    assert "openvpn" in keys
    assert "wireguard" in keys


@pytest.mark.asyncio
async def test_get_states_handles_missing_method_and_calls(
    make_config_entry, fake_client
) -> None:
    """_get_states should skip missing client methods and return available states."""
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=make_config_entry(),
    )
    categories = [
        {"function": "get_telemetry", "state_key": "telemetry"},
        {"function": "nonexistent_method", "state_key": "bad"},
    ]
    state = await coord._get_states(categories)
    assert "telemetry" in state
    assert "bad" not in state


@pytest.mark.asyncio
async def test_get_states_uses_single_carp_call(
    make_config_entry: Any, fake_client: Any
) -> None:
    """Coordinator fetches unified CARP payload with a single client call."""
    client = fake_client()()
    client.get_carp = AsyncMock(
        return_value={
            "interfaces": [
                {"interface": "wan", "subnet": "1.2.3.4", "status": "MASTER"}
            ],
            "status_summary": {"state": "healthy", "vip_count": 1},
        }
    )
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=make_config_entry(),
    )

    state = await coord._get_states([{"function": "get_carp", "state_key": "carp"}])
    client.get_carp.assert_awaited_once()
    assert state["carp"]["interfaces"][0]["status"] == "MASTER"
    assert state["carp"]["status_summary"]["state"] == "healthy"


@pytest.mark.asyncio
async def test_check_device_unique_id_mismatch_triggers_issue(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """Mismatched device_unique_id should create an issue and shutdown after threshold."""
    entry = make_config_entry({CONF_DEVICE_UNIQUE_ID: "expected"})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="expected",
        config_entry=entry,
    )

    # state missing device_unique_id -> returns False and resets count
    coord._state = {}
    res = await coord._check_device_unique_id()
    assert res is False
    assert coord._mismatched_count == 0

    # state present but mismatched -> increments and eventually triggers issue
    coord._state = {"device_unique_id": "other"}
    # patch issue registry and async_shutdown to avoid side effects
    called = {"issue": 0, "shutdown": 0, "issue_kwargs": None}

    async def fake_shutdown():
        called["shutdown"] += 1

    def fake_async_create_issue(**kwargs):
        # record the kwargs so tests can validate domain and issue_id
        called["issue"] += 1
        called["issue_kwargs"] = kwargs

    monkeypatch.setattr(
        coordinator_module.ir, "async_create_issue", fake_async_create_issue
    )
    coord.async_shutdown = fake_shutdown

    # call 3 times -> should call issue once and shutdown once
    await coord._check_device_unique_id()
    await coord._check_device_unique_id()
    await coord._check_device_unique_id()
    assert coord._mismatched_count == 3
    assert called["issue"] == 1
    assert called["shutdown"] == 1
    # validate the issue was created for the integration domain and expected id
    assert isinstance(called["issue_kwargs"], MutableMapping)
    assert called["issue_kwargs"].get("domain") == coordinator_module.DOMAIN
    assert (
        called["issue_kwargs"].get("issue_id")
        == f"{coord._device_unique_id}_device_id_mismatched"
    )


@pytest.mark.asyncio
async def test_calculate_speed_normal_and_exception() -> None:
    """Calculate speed handles normal and exceptional (zero elapsed) cases."""
    # normal pkts
    new_prop, value = await OPNsenseDataUpdateCoordinator._calculate_speed(
        prop_name="inpkts",
        elapsed_time=2.0,
        current_parent_value=200,
        previous_parent_value=100,
    )
    assert new_prop == "inpkts_packets_per_second"
    assert isinstance(value, int)
    assert value == 50

    # zero elapsed_time -> exception handled -> rate 0
    _new_prop2, value2 = await OPNsenseDataUpdateCoordinator._calculate_speed(
        prop_name="inpkts",
        elapsed_time=0,
        current_parent_value=10,
        previous_parent_value=5,
    )
    assert value2 == 0


@pytest.mark.asyncio
async def test_calculate_entity_speeds_applies_calculations(
    make_config_entry, fake_client
) -> None:
    """Entity speed calculations should add correct rate keys to state."""
    entry = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "id", CONF_SYNC_INTERFACES: True, CONF_SYNC_VPN: True}
    )
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    # set up state and previous_state with times
    now = time.time()
    coord._state = {
        "update_time": now,
        "interfaces": {
            "eth0": {"inbytes": 200, "outbytes": 100, "inpkts": 300, "outpkts": 150}
        },
        "openvpn": {
            "servers": {"s1": {"total_bytes_recv": 1000, "total_bytes_sent": 2000}}
        },
        "previous_state": {
            "update_time": now - 2,
            "interfaces": {
                "eth0": {"inbytes": 100, "outbytes": 50, "inpkts": 100, "outpkts": 50}
            },
            "openvpn": {
                "servers": {"s1": {"total_bytes_recv": 500, "total_bytes_sent": 1000}}
            },
        },
    }

    # calculate speeds and assert expected rate fields exist with correct values
    await coord._calculate_entity_speeds()

    # delta_time between now and previous_state is 2 seconds
    # coordinator stores byte rates as kilobytes_per_second (rounded) and
    # packet rates as packets_per_second (rounded). Assert those keys/values.
    assert "interfaces" in coord._state
    eth0 = coord._state["interfaces"]["eth0"]
    # byte rates -> kilobytes_per_second (rounded)
    assert "inbytes_kilobytes_per_second" in eth0
    assert "outbytes_kilobytes_per_second" in eth0
    # packet rates -> packets_per_second
    assert "inpkts_packets_per_second" in eth0
    assert "outpkts_packets_per_second" in eth0

    # Compute expected rounded values
    # inbytes: change = 100 B/s -> 100 / 2 = 50 B/s -> 50 / 1000 = 0.05 KB/s -> round = 0
    # outbytes: change = 50 B/s -> 25 B/s -> 0.025 KB/s -> round = 0
    assert eth0["inbytes_kilobytes_per_second"] == pytest.approx(0.5, abs=0.5)
    assert eth0["outbytes_kilobytes_per_second"] == pytest.approx(0.5, abs=0.5)
    assert eth0["inpkts_packets_per_second"] == pytest.approx(100, abs=0.5)
    assert eth0["outpkts_packets_per_second"] == pytest.approx(50, abs=0.5)

    # openvpn server s1 expected rates (kilobytes_per_second, rounded)
    assert "openvpn" in coord._state
    assert "servers" in coord._state["openvpn"]
    s1 = coord._state["openvpn"]["servers"]["s1"]
    assert "total_bytes_recv_kilobytes_per_second" in s1
    assert "total_bytes_sent_kilobytes_per_second" in s1
    # total_bytes_recv: (1000-500)/2 = 250 B/s -> 0.25 KB/s -> round = 0
    # total_bytes_sent: (2000-1000)/2 = 500 B/s -> 0.5 KB/s -> round = 0
    assert s1["total_bytes_recv_kilobytes_per_second"] == pytest.approx(0.5, abs=0.5)
    assert s1["total_bytes_sent_kilobytes_per_second"] == pytest.approx(0.5, abs=0.5)


@pytest.mark.asyncio
async def test_calculate_entity_speeds_handles_counter_rollover(
    make_config_entry, fake_client
) -> None:
    """Regression: ensure rates never go negative when counters decrease (device reset/rollback)."""
    entry = make_config_entry(
        {CONF_DEVICE_UNIQUE_ID: "id", CONF_SYNC_INTERFACES: True, CONF_SYNC_VPN: True}
    )
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    # Now simulate a rollback: previous counters larger than current
    now = time.time()
    coord._state = {
        "update_time": now,
        "interfaces": {
            "eth0": {"inbytes": 100, "outbytes": 50, "inpkts": 10, "outpkts": 5}
        },
        "openvpn": {
            "servers": {"s1": {"total_bytes_recv": 100, "total_bytes_sent": 200}}
        },
        "previous_state": {
            "update_time": now - 2,
            "interfaces": {
                "eth0": {
                    "inbytes": 1000,
                    "outbytes": 500,
                    "inpkts": 1000,
                    "outpkts": 500,
                }
            },
            "openvpn": {
                "servers": {"s1": {"total_bytes_recv": 1000, "total_bytes_sent": 2000}}
            },
        },
    }

    # run calculation; code should clamp or avoid negative rates
    await coord._calculate_entity_speeds()

    # interfaces rates exist and are non-negative
    eth0 = coord._state["interfaces"]["eth0"]
    assert "inbytes_kilobytes_per_second" in eth0
    assert "outbytes_kilobytes_per_second" in eth0
    assert "inpkts_packets_per_second" in eth0
    assert "outpkts_packets_per_second" in eth0
    assert eth0["inbytes_kilobytes_per_second"] >= 0
    assert eth0["outbytes_kilobytes_per_second"] >= 0
    assert eth0["inpkts_packets_per_second"] >= 0
    assert eth0["outpkts_packets_per_second"] >= 0

    # openvpn rates exist and are non-negative
    s1 = coord._state["openvpn"]["servers"]["s1"]
    assert "total_bytes_recv_kilobytes_per_second" in s1
    assert "total_bytes_sent_kilobytes_per_second" in s1
    assert s1["total_bytes_recv_kilobytes_per_second"] >= 0
    assert s1["total_bytes_sent_kilobytes_per_second"] >= 0


@pytest.mark.asyncio
async def test_async_update_data_reentrancy_and_full_flow(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """End-to-end coordinator update flow and reentrancy behavior."""
    entry = make_config_entry({CONF_DEVICE_UNIQUE_ID: "id", CONF_SYNC_INTERFACES: True})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    # reentrancy: set updating True
    coord._updating = True
    res = await coord._async_update_data()
    assert res == coord._state
    coord._updating = False

    # full flow: monkeypatch _check_device_unique_id to True and ensure functions called
    async def true_check():
        return True

    monkeypatch.setattr(coord, "_check_device_unique_id", true_check)

    # ensure calculate_entity_speeds is callable
    async def fake_calc():
        return None

    monkeypatch.setattr(coord, "_calculate_entity_speeds", fake_calc)
    # Spy on client's reset_query_counts before running the update so we can
    # assert the public method was awaited during the update flow.
    client.reset_query_counts = AsyncMock(
        wraps=getattr(client, "reset_query_counts", None)
    )

    # run update; should return a dict
    out = await coord._async_update_data()
    assert isinstance(out, MutableMapping)
    # Verify returned dict is the coordinator's state and bookkeeping completed
    assert out == coord._state
    assert coord._updating is False
    # Ensure a last-update marker exists via DataUpdateCoordinator API
    assert isinstance(coord.last_update_success, bool)
    # And the client.reset_query_counts public method was awaited exactly once
    client.reset_query_counts.assert_awaited_once()


@pytest.mark.asyncio
async def test_calculate_speed_bytes_case() -> None:
    """Calculate byte-rate conversion yields kilobytes_per_second."""
    # bytes branch should return kilobytes_per_second label
    new_prop, value = await OPNsenseDataUpdateCoordinator._calculate_speed(
        prop_name="inbytes",
        elapsed_time=2.0,
        current_parent_value=2000,
        previous_parent_value=1000,
    )
    assert new_prop == "inbytes_kilobytes_per_second"
    assert isinstance(value, int)
    assert value == pytest.approx(
        0.5, abs=0.5
    )  # 500 B/s -> 0.5 KB/s, allow ±0.5 tolerance


def test_build_categories_returns_empty_when_no_config(
    make_config_entry, fake_client
) -> None:
    """Categories builder returns empty list when config_entry is missing."""
    entry = make_config_entry()
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )
    # simulate missing config_entry
    coord.config_entry = None
    cats = coord._build_categories()
    assert cats == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag", "expected_keys"),
    [
        (CONF_SYNC_TELEMETRY, ["telemetry"]),
        (CONF_SYNC_VNSTAT, ["vnstat"]),
        (CONF_SYNC_SPEEDTEST, ["speedtest"]),
        (CONF_SYNC_VPN, ["openvpn", "wireguard"]),
        (CONF_SYNC_FIRMWARE_UPDATES, ["firmware_update_info"]),
        (CONF_SYNC_CARP, ["carp"]),
        (CONF_SYNC_DHCP_LEASES, ["dhcp_leases"]),
        (CONF_SYNC_GATEWAYS, ["gateways"]),
        (CONF_SYNC_SERVICES, ["services"]),
        (CONF_SYNC_NOTICES, ["notices"]),
        (CONF_SYNC_FIREWALL_AND_NAT, ["firewall"]),
        (CONF_SYNC_UNBOUND, [ATTR_UNBOUND_BLOCKLIST]),
        (CONF_SYNC_INTERFACES, ["interfaces"]),
        (CONF_SYNC_CERTIFICATES, ["certificates"]),
    ],
)
async def test_build_categories_flag_true_and_false(
    make_config_entry, fake_client, flag, expected_keys
) -> None:
    """Verify categories include keys when flag True and exclude when False."""
    # When flag is True -> expected keys present
    entry_true = make_config_entry({"device_unique_id": "id", flag: True})
    client = fake_client()()
    coord_true = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry_true,
    )
    keys_true = [c["state_key"] for c in coord_true._categories]
    for ek in expected_keys:
        assert ek in keys_true

    # When flag is False -> expected keys absent
    entry_false = make_config_entry({"device_unique_id": "id", flag: False})
    coord_false = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry_false,
    )
    keys_false = [c["state_key"] for c in coord_false._categories]
    for ek in expected_keys:
        assert ek not in keys_false


@pytest.mark.asyncio
async def test_async_update_data_strips_nested_previous_state(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """Ensure nested 'previous_state' key is removed from the copied previous_state.

    The coordinator copies its current _state into previous_state, then removes any
    nested 'previous_state' key from that copy before assigning it back. This test
    verifies that behavior.
    """
    entry = make_config_entry({"device_unique_id": "id", CONF_SYNC_INTERFACES: True})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    # Prepare a state that contains a nested 'previous_state' key which should be stripped
    coord._state = {
        "previous_state": {"inner": 1},
        "device_unique_id": "id",
        "extra": "keep",
    }

    # Make device id check pass and skip heavy calculations
    async def true_check():
        return True

    async def noop_calc():
        return None

    monkeypatch.setattr(coord, "_check_device_unique_id", true_check)
    monkeypatch.setattr(coord, "_calculate_entity_speeds", noop_calc)

    # Spy on reset_query_counts to ensure update flow runs
    client.reset_query_counts = AsyncMock(
        wraps=getattr(client, "reset_query_counts", None)
    )

    out = await coord._async_update_data()

    # previous_state assigned on the coordinator should not contain the nested key
    assert isinstance(out, MutableMapping)
    assert "previous_state" in out
    assert "previous_state" not in out["previous_state"]
    # other top-level keys from the original state should be preserved in the copy
    assert out["previous_state"].get("device_unique_id") == "id"
    assert out["previous_state"].get("extra") == "keep"


@pytest.mark.asyncio
async def test_async_update_data_device_tracker_branch(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """When coordinator is a device tracker coordinator, _async_update_data should return _async_update_dt_data result."""
    entry = make_config_entry({"device_unique_id": "id"})
    client = fake_client()()
    # create coordinator as device tracker coordinator
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
        device_tracker_coordinator=True,
    )

    # patch the device tracker update to return a specific dict and record calls
    called = {"dt_called": 0}

    async def fake_dt_update():
        called["dt_called"] += 1
        return {"dt": True}

    monkeypatch.setattr(coord, "_async_update_dt_data", fake_dt_update)

    # spy on client's reset_query_counts
    client.reset_query_counts = AsyncMock(
        wraps=getattr(client, "reset_query_counts", None)
    )

    res = await coord._async_update_data()
    assert res == {"dt": True}
    assert called["dt_called"] == 1
    client.reset_query_counts.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_update_data_wraps_refresh_errors(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """Coordinator refresh errors should be exposed as UpdateFailed."""
    entry = make_config_entry({"device_unique_id": "id"})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    async def raising_get_states(_categories):
        raise RuntimeError("boom")

    monkeypatch.setattr(coord, "_get_states", raising_get_states)

    with pytest.raises(UpdateFailed, match="Failed to refresh OPNsense data: boom"):
        await coord._async_update_data()

    assert coord._updating is False


@pytest.mark.asyncio
async def test_async_update_data_returns_empty_when_device_id_check_fails(
    monkeypatch: pytest.MonkeyPatch, make_config_entry, fake_client
) -> None:
    """When device unique id check fails, _async_update_data should return an empty dict."""
    entry = make_config_entry({"device_unique_id": "id", CONF_SYNC_INTERFACES: True})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    async def false_check():
        return False

    # make the device id check return False
    monkeypatch.setattr(coord, "_check_device_unique_id", false_check)

    # spy on reset_query_counts
    client.reset_query_counts = AsyncMock(
        wraps=getattr(client, "reset_query_counts", None)
    )

    res = await coord._async_update_data()

    assert res == {}
    client.reset_query_counts.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["no_previous", "no_config"])
async def test_calculate_entity_speeds_returns_early_when_missing(
    case, make_config_entry, fake_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_calculate_entity_speeds should return early when previous_update_time is falsy or config_entry is falsy."""
    entry = make_config_entry(
        {"device_unique_id": "id", CONF_SYNC_INTERFACES: True, CONF_SYNC_VPN: True}
    )
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    now = time.time()
    if case == "no_previous":
        # update_time present but previous_state.update_time missing -> early return
        coord._state = {"update_time": now, "previous_state": {}}
    else:
        # previous_update_time present but config_entry falsy -> early return
        coord._state = {"update_time": now, "previous_state": {"update_time": now - 2}}
        coord.config_entry = None

    # Ensure the deeper calculation functions are not called when guard triggers
    coord._calculate_interface_speeds = AsyncMock(
        side_effect=AssertionError("_calculate_interface_speeds should not be called")
    )
    coord._calculate_vpn_speeds = AsyncMock(
        side_effect=AssertionError("_calculate_vpn_speeds should not be called")
    )

    # Call the method; it should return None and not call the mocked methods
    res = await coord._calculate_entity_speeds()
    assert res is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("returned_device_id", "should_call_counts"),
    [
        (None, False),
        ("other", False),
        ("id", True),
    ],
)
async def test_async_update_dt_data_device_id_branches(
    returned_device_id,
    should_call_counts,
    make_config_entry,
    fake_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _async_update_dt_data returns early for missing/mismatched IDs and calls query counts when OK."""
    entry = make_config_entry({"device_unique_id": "id"})
    client = fake_client()()
    coord = OPNsenseDataUpdateCoordinator(
        hass=MagicMock(),
        client=client,
        name="n",
        update_interval=timedelta(seconds=1),
        device_unique_id="id",
        config_entry=entry,
    )

    # stub _get_states to return controlled values
    fake_state = {
        "device_unique_id": returned_device_id,
        "host_firmware_version": "fv",
        "system_info": {"name": "opn"},
        "arp_table": {"a": 1},
    }

    async def fake_get_states(categories):
        return fake_state

    monkeypatch.setattr(coord, "_get_states", fake_get_states)

    # spy on client's get_query_counts
    client.get_query_counts = AsyncMock(return_value=3)

    res = await coord._async_update_dt_data()

    if should_call_counts:
        # Should return the state and call get_query_counts
        assert isinstance(res, MutableMapping)
        assert res.get("device_unique_id") == "id"
        client.get_query_counts.assert_awaited_once()
    else:
        # Should return empty dict and not call get_query_counts
        assert res == {}
        assert client.get_query_counts.await_count == 0
