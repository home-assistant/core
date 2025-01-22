"""The tests for the bluetooth WebSocket API."""

import asyncio
from datetime import timedelta
import time
from unittest.mock import ANY, patch

from bleak_retry_connector import Allocations
from freezegun import freeze_time
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from . import (
    HCI0_SOURCE_ADDRESS,
    HCI1_SOURCE_ADDRESS,
    NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_source,
)

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("enable_bluetooth")
async def test_subscribe_advertisements(
    hass: HomeAssistant,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test bluetooth subscribe_advertisements."""
    address = "44:44:33:11:23:12"

    switchbot_device_signal_100 = generate_ble_device(
        address, "wohand_signal_100", rssi=-100
    )
    switchbot_adv_signal_100 = generate_advertisement_data(
        local_name="wohand_signal_100", service_uuids=[]
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, HCI0_SOURCE_ADDRESS
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "bluetooth/subscribe_advertisements",
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["success"]

    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "address": "44:44:33:11:23:12",
                "connectable": True,
                "manufacturer_data": {},
                "name": "wohand_signal_100",
                "rssi": -127,
                "service_data": {},
                "service_uuids": [],
                "source": HCI0_SOURCE_ADDRESS,
                "time": ANY,
                "tx_power": -127,
            }
        ]
    }
    adv_time = response["event"]["add"][0]["time"]

    switchbot_adv_signal_100 = generate_advertisement_data(
        local_name="wohand_signal_100",
        manufacturer_data={123: b"abc"},
        service_uuids=[],
        rssi=-80,
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, HCI1_SOURCE_ADDRESS
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "address": "44:44:33:11:23:12",
                "connectable": True,
                "manufacturer_data": {"123": "616263"},
                "name": "wohand_signal_100",
                "rssi": -80,
                "service_data": {},
                "service_uuids": [],
                "source": HCI1_SOURCE_ADDRESS,
                "time": ANY,
                "tx_power": -127,
            }
        ]
    }
    new_time = response["event"]["add"][0]["time"]
    assert new_time > adv_time
    future_time = utcnow() + timedelta(seconds=3600)
    future_monotonic_time = time.monotonic() + 3600
    with (
        freeze_time(future_time),
        patch(
            "habluetooth.manager.monotonic_time_coarse",
            return_value=future_monotonic_time,
        ),
    ):
        async_fire_time_changed(hass, future_time)
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {"remove": [{"address": "44:44:33:11:23:12"}]}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_subscribe_subscribe_connection_allocations(
    hass: HomeAssistant,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
    register_non_connectable_scanner: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test bluetooth subscribe_connection_allocations."""
    address = "44:44:33:11:23:12"

    switchbot_device_signal_100 = generate_ble_device(
        address, "wohand_signal_100", rssi=-100
    )
    switchbot_adv_signal_100 = generate_advertisement_data(
        local_name="wohand_signal_100", service_uuids=[]
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, HCI0_SOURCE_ADDRESS
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "bluetooth/subscribe_connection_allocations",
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["success"]

    async with asyncio.timeout(1):
        response = await client.receive_json()

    assert response["event"] == [
        {
            "allocated": [],
            "free": 0,
            "slots": 0,
            "source": NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS,
        }
    ]

    manager = _get_manager()
    manager.async_on_allocation_changed(
        Allocations(
            adapter="hci1",  # Will be translated to source
            slots=5,
            free=4,
            allocated=["AA:BB:CC:DD:EE:EE"],
        )
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == [
        {
            "allocated": ["AA:BB:CC:DD:EE:EE"],
            "free": 4,
            "slots": 5,
            "source": "AA:BB:CC:DD:EE:11",
        }
    ]
    manager.async_on_allocation_changed(
        Allocations(
            adapter="hci1",  # Will be translated to source
            slots=5,
            free=5,
            allocated=[],
        )
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == [
        {"allocated": [], "free": 5, "slots": 5, "source": HCI1_SOURCE_ADDRESS}
    ]


@pytest.mark.usefixtures("enable_bluetooth")
async def test_subscribe_subscribe_connection_allocations_specific_scanner(
    hass: HomeAssistant,
    register_non_connectable_scanner: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test bluetooth subscribe_connection_allocations for a specific source address."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "bluetooth/subscribe_connection_allocations",
            "source": NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS,
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["success"]

    async with asyncio.timeout(1):
        response = await client.receive_json()

    assert response["event"] == [
        {
            "allocated": [],
            "free": 0,
            "slots": 0,
            "source": NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS,
        }
    ]


@pytest.mark.usefixtures("enable_bluetooth")
async def test_subscribe_subscribe_connection_allocations_invalid_scanner(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test bluetooth subscribe_connection_allocations for an invalid source address."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "bluetooth/subscribe_connection_allocations",
            "source": "90:00:00:00:00:00",
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_source"
    assert response["error"]["message"] == "Invalid source"
