"""Test the device level APIs."""

import asyncio
from unittest.mock import patch

from pyinsteon.constants import DeviceAction
from pyinsteon.topics import DEVICE_LIST_CHANGED
from pyinsteon.utils import publish_topic
import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.api.device import (
    DEVICE_ID,
    HA_DEVICE_NOT_FOUND,
    ID,
    INSTEON_DEVICE_NOT_FOUND,
    TYPE,
)
from homeassistant.components.insteon.const import (
    CONF_OVERRIDE,
    CONF_X10,
    DOMAIN,
    MULTIPLE,
)
from homeassistant.components.insteon.utils import async_device_name
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices
from .mock_setup import async_mock_setup

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_get_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting an Insteon device."""

    ws_client, devices, ha_device, _ = await async_mock_setup(hass, hass_ws_client)
    with patch.object(insteon.api.device, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/device/get", DEVICE_ID: ha_device.id}
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

        assert result["name"] == "Device 11.11.11"
        assert result["address"] == "11.11.11"


async def test_no_ha_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test response when no HA device exists."""

    ws_client, devices, _, _ = await async_mock_setup(hass, hass_ws_client)
    with patch.object(insteon.api.device, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/device/get", DEVICE_ID: "not_a_device"}
        )
        msg = await ws_client.receive_json()
        assert not msg.get("result")
        assert msg.get("error")
        assert msg["error"]["message"] == HA_DEVICE_NOT_FOUND


async def test_no_insteon_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test response when no Insteon device exists."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="abcde12345",
        data=MOCK_USER_INPUT_PLM,
        options={},
    )
    config_entry.add_to_hass(hass)
    async_load_api(hass)

    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()

    # Create device registry entry for a Insteon device not in the Insteon devices list
    ha_device_1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "AA.BB.CC")},
        name="HA Device Only",
    )
    # Create device registry entry for a non-Insteon device
    ha_device_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("other_domain", "no address")},
        name="HA Device Only",
    )
    with patch.object(insteon.api.device, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/device/get", DEVICE_ID: ha_device_1.id}
        )
        msg = await ws_client.receive_json()
        assert not msg.get("result")
        assert msg.get("error")
        assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND

        await ws_client.send_json(
            {ID: 3, TYPE: "insteon/device/get", DEVICE_ID: ha_device_2.id}
        )
        msg = await ws_client.receive_json()
        assert not msg.get("result")
        assert msg.get("error")
        assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND


async def test_get_ha_device_name(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the HA device name from an Insteon address."""

    _, devices, _, device_reg = await async_mock_setup(hass, hass_ws_client)

    with patch.object(insteon.api.device, "devices", devices):
        # Test a real HA and Insteon device
        name = await async_device_name(device_reg, "11.11.11")
        assert name == "Device 11.11.11"

        # Test no HA or Insteon device
        name = await async_device_name(device_reg, "BB.BB.BB")
        assert name == ""


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_add_device_api(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding an Insteon device."""

    ws_client, devices, _, _ = await async_mock_setup(hass, hass_ws_client)
    with patch.object(insteon.api.device, "devices", devices):
        await ws_client.send_json({ID: 2, TYPE: "insteon/device/add", MULTIPLE: True})

        await asyncio.sleep(0.01)
        assert devices.async_add_device_called_with.get("address") is None
        assert devices.async_add_device_called_with["multiple"] is True

        msg = await ws_client.receive_json()
        assert msg["event"]["type"] == "device_added"
        assert msg["event"]["address"] == "aa.bb.cc"

        msg = await ws_client.receive_json()
        assert msg["event"]["type"] == "device_added"
        assert msg["event"]["address"] == "bb.cc.dd"

        publish_topic(
            DEVICE_LIST_CHANGED,
            address=None,
            action=DeviceAction.COMPLETED,
        )
        msg = await ws_client.receive_json()
        assert msg["event"]["type"] == "linking_stopped"


async def test_cancel_add_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test cancelling adding of a new device."""

    ws_client, devices, _, _ = await async_mock_setup(hass, hass_ws_client)

    with patch.object(insteon.api.aldb, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/device/add/cancel",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]


async def test_add_x10_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding an X10 device."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    x10_device = {"housecode": "a", "unitcode": 1, "platform": "switch"}
    await ws_client.send_json(
        {ID: 2, TYPE: "insteon/device/add_x10", "x10_device": x10_device}
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_X10]) == 1
    assert config_entry.options[CONF_X10][0]["housecode"] == "a"
    assert config_entry.options[CONF_X10][0]["unitcode"] == 1
    assert config_entry.options[CONF_X10][0]["platform"] == "switch"


async def test_add_x10_device_duplicate(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a duplicate X10 device."""

    x10_device = {"housecode": "a", "unitcode": 1, "platform": "switch"}

    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options={CONF_X10: [x10_device]}
    )
    await ws_client.send_json(
        {ID: 2, TYPE: "insteon/device/add_x10", "x10_device": x10_device}
    )
    msg = await ws_client.receive_json()
    assert msg["error"]
    assert msg["error"]["code"] == "duplicate"


async def test_remove_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing an Insteon device."""
    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/device/remove",
            "device_address": "11.22.33",
            "remove_all_refs": True,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]


async def test_remove_x10_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing an X10 device."""
    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/device/remove",
            "device_address": "X10.A.01",
            "remove_all_refs": True,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]


async def test_remove_one_x10_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test one X10 device without removing others."""
    x10_device = {"housecode": "a", "unitcode": 1, "platform": "light", "dim_steps": 22}
    x10_devices = [
        x10_device,
        {"housecode": "a", "unitcode": 2, "platform": "switch"},
    ]
    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options={CONF_X10: x10_devices}
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/device/remove",
            "device_address": "X10.A.01",
            "remove_all_refs": True,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_X10]) == 1
    assert config_entry.options[CONF_X10][0]["housecode"] == "a"
    assert config_entry.options[CONF_X10][0]["unitcode"] == 2


async def test_remove_device_with_overload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing an Insteon device that has a device overload."""
    overload = {"address": "99.99.99", "cat": 1, "subcat": 3}
    overloads = {CONF_OVERRIDE: [overload]}
    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options=overloads
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/device/remove",
            "device_address": "99.99.99",
            "remove_all_refs": True,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert not config_entry.options.get(CONF_OVERRIDE)
