"""Test the Insteon All-Link Database APIs."""

import json
from unittest.mock import patch

from pyinsteon import pub
from pyinsteon.address import Address
from pyinsteon.topics import ALDB_STATUS_CHANGED, DEVICE_LINK_CONTROLLER_CREATED
import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.api.aldb import (
    ALDB_RECORD,
    DEVICE_ADDRESS,
    ID,
    TYPE,
)
from homeassistant.components.insteon.api.device import INSTEON_DEVICE_NOT_FOUND

from .mock_devices import MockDevices

from tests.common import load_fixture


@pytest.fixture(name="aldb_data", scope="session")
def aldb_data_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("insteon/aldb_data.json"))


async def _setup(hass, hass_ws_client, aldb_data):
    """Set up tests."""
    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()
    async_load_api(hass)
    devices.fill_aldb("33.33.33", aldb_data)
    return ws_client, devices


def _compare_records(aldb_rec, dict_rec):
    """Compare a record in the ALDB to the dictionary record."""
    assert aldb_rec.is_in_use == dict_rec["in_use"]
    assert aldb_rec.is_controller == (dict_rec["is_controller"])
    assert not aldb_rec.is_high_water_mark
    assert aldb_rec.group == dict_rec["group"]
    assert aldb_rec.target == Address(dict_rec["target"])
    assert aldb_rec.data1 == dict_rec["data1"]
    assert aldb_rec.data2 == dict_rec["data2"]
    assert aldb_rec.data3 == dict_rec["data3"]


def _aldb_dict(mem_addr):
    """Generate an ALDB record as a dictionary."""
    return {
        "mem_addr": mem_addr,
        "in_use": True,
        "is_controller": True,
        "highwater": False,
        "group": 100,
        "target": "111111",
        "data1": 101,
        "data2": 102,
        "data3": 103,
        "dirty": True,
    }


async def test_get_aldb(hass, hass_ws_client, aldb_data):
    """Test getting an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/aldb/get", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

        assert len(result) == 5


async def test_change_aldb_record(hass, hass_ws_client, aldb_data):
    """Test changing an Insteon device's All-Link Database record."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)
    change_rec = _aldb_dict(4079)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/change",
                DEVICE_ADDRESS: "33.33.33",
                ALDB_RECORD: change_rec,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(devices["33.33.33"].aldb.pending_changes) == 1
        rec = devices["33.33.33"].aldb.pending_changes[4079]
        _compare_records(rec, change_rec)


async def test_create_aldb_record(hass, hass_ws_client, aldb_data):
    """Test creating a new Insteon All-Link Database record."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)
    new_rec = _aldb_dict(4079)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/create",
                DEVICE_ADDRESS: "33.33.33",
                ALDB_RECORD: new_rec,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(devices["33.33.33"].aldb.pending_changes) == 1
        rec = devices["33.33.33"].aldb.pending_changes[-1]
        _compare_records(rec, new_rec)


async def test_write_aldb(hass, hass_ws_client, aldb_data):
    """Test writing an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/write",
                DEVICE_ADDRESS: "33.33.33",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].aldb.async_write.call_count == 1
        assert devices["33.33.33"].aldb.async_load.call_count == 1
        assert devices.async_save.call_count == 1


async def test_load_aldb(hass, hass_ws_client, aldb_data):
    """Test loading an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/load",
                DEVICE_ADDRESS: "AA.AA.AA",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["AA.AA.AA"].aldb.async_load.call_count == 1
        assert devices.async_save.call_count == 1


async def test_reset_aldb(hass, hass_ws_client, aldb_data):
    """Test resetting an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)
    record = _aldb_dict(4079)
    devices["33.33.33"].aldb.modify(
        mem_addr=record["mem_addr"],
        in_use=record["in_use"],
        group=record["group"],
        controller=record["is_controller"],
        target=record["target"],
        data1=record["data1"],
        data2=record["data2"],
        data3=record["data3"],
    )

    assert devices["33.33.33"].aldb.pending_changes
    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/reset",
                DEVICE_ADDRESS: "33.33.33",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert not devices["33.33.33"].aldb.pending_changes


async def test_default_links(hass, hass_ws_client, aldb_data):
    """Test getting an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/add_default_links",
                DEVICE_ADDRESS: "33.33.33",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].async_add_default_links.call_count == 1
        assert devices["33.33.33"].aldb.async_load.call_count == 1
        assert devices.async_save.call_count == 1


async def test_notify_on_aldb_status(hass, hass_ws_client, aldb_data):
    """Test getting an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/notify",
                DEVICE_ADDRESS: "33.33.33",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        pub.sendMessage(f"333333.{ALDB_STATUS_CHANGED}")
        msg = await ws_client.receive_json()
        assert msg["event"]["type"] == "status_changed"
        assert not msg["event"]["is_loading"]


async def test_notify_on_aldb_record_added(hass, hass_ws_client, aldb_data):
    """Test getting an Insteon device's All-Link Database."""
    ws_client, devices = await _setup(hass, hass_ws_client, aldb_data)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/aldb/notify",
                DEVICE_ADDRESS: "33.33.33",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        pub.sendMessage(
            f"{DEVICE_LINK_CONTROLLER_CREATED}.333333",
            controller=Address("11.11.11"),
            responder=Address("33.33.33"),
            group=100,
        )
        msg = await ws_client.receive_json()
        assert msg["event"]["type"] == "record_loaded"


async def test_bad_address(hass, hass_ws_client, aldb_data):
    """Test for a bad Insteon address."""
    ws_client, _ = await _setup(hass, hass_ws_client, aldb_data)
    record = _aldb_dict(0)

    ws_id = 0
    for call in ["get", "write", "load", "reset", "add_default_links", "notify"]:
        ws_id += 1
        await ws_client.send_json(
            {
                ID: ws_id,
                TYPE: f"insteon/aldb/{call}",
                DEVICE_ADDRESS: "99.99.99",
            }
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND

    for call in ["change", "create"]:
        ws_id += 1
        await ws_client.send_json(
            {
                ID: ws_id,
                TYPE: f"insteon/aldb/{call}",
                DEVICE_ADDRESS: "99.99.99",
                ALDB_RECORD: record,
            }
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND
