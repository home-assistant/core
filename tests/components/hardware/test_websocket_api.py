"""Test the hardware websocket API."""
from collections import namedtuple
import datetime
from unittest.mock import patch

from homeassistant.components.hardware.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_board_info(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can get the board info."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"hardware": []}


TEST_TIME_ADVANCE_INTERVAL = datetime.timedelta(seconds=5 + 1)


async def test_system_status_subscription(hass: HomeAssistant, hass_ws_client, freezer):
    """Test websocket system status subscription."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/subscribe_system_status"})
    response = await client.receive_json()
    assert response["success"]

    VirtualMem = namedtuple("VirtualMemory", ["available", "percent", "total"])
    vmem = VirtualMem(10 * 1024**2, 50, 30 * 1024**2)

    with patch.object(
        hass.data[DOMAIN]["system_status"].ha_psutil.psutil,
        "cpu_percent",
        return_value=123,
    ), patch.object(
        hass.data[DOMAIN]["system_status"].ha_psutil.psutil,
        "virtual_memory",
        return_value=vmem,
    ):
        freezer.tick(TEST_TIME_ADVANCE_INTERVAL)
        await hass.async_block_till_done()

    response = await client.receive_json()
    assert response["event"] == {
        "cpu_percent": 123,
        "memory_free_mb": 10.0,
        "memory_used_mb": 20.0,
        "memory_used_percent": 50,
        "timestamp": dt_util.utcnow().isoformat(),
    }

    # Unsubscribe
    await client.send_json({"id": 8, "type": "unsubscribe_events", "subscription": 1})
    response = await client.receive_json()
    assert response["success"]

    with patch.object(
        hass.data[DOMAIN]["system_status"].ha_psutil.psutil, "cpu_percent"
    ) as cpu_mock, patch.object(
        hass.data[DOMAIN]["system_status"].ha_psutil.psutil, "virtual_memory"
    ) as vmem_mock:
        freezer.tick(TEST_TIME_ADVANCE_INTERVAL)
        await hass.async_block_till_done()
        cpu_mock.assert_not_called()
        vmem_mock.assert_not_called()
