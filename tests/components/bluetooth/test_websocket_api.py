"""The tests for the bluetooth WebSocket API."""

import asyncio
from unittest.mock import ANY

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant

from . import (
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_source,
)

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("enable_bluetooth")
async def test_subscribe_advertisements(
    hass: HomeAssistant,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
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
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, "hci0"
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
                "source": "hci0",
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
    freezer.tick(1)
    inject_advertisement_with_source(
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, "hci1"
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
                "source": "hci1",
                "time": ANY,
                "tx_power": -127,
            }
        ]
    }
    new_time = response["event"]["add"][0]["time"]
    assert new_time > adv_time
    manager = _get_manager()
    freezer.tick(3600)
    manager._async_check_unavailable()
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {"remove": [{"address": "44:44:33:11:23:12"}]}
