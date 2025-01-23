"""Test the Insteon APIs for configuring the integration."""

import asyncio
import json
from unittest.mock import patch

from homeassistant.components import insteon
from homeassistant.components.insteon.api.device import ID, TYPE
from homeassistant.components.insteon.const import (
    CONF_HUB_VERSION,
    CONF_OVERRIDE,
    CONF_X10,
)
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_DEVICE,
    MOCK_HOSTNAME,
    MOCK_USER_INPUT_HUB_V1,
    MOCK_USER_INPUT_HUB_V2,
    MOCK_USER_INPUT_PLM,
)
from .mock_connection import mock_failed_connection, mock_successful_connection
from .mock_devices import MockDevices
from .mock_setup import async_mock_setup

from tests.common import load_fixture
from tests.typing import WebSocketGenerator


class MockProtocol:
    """A mock Insteon protocol object."""

    connected = True


async def test_get_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon configuration."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    await ws_client.send_json({ID: 2, TYPE: "insteon/config/get"})
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result["modem_config"] == {"device": MOCK_DEVICE}


async def test_get_modem_schema_plm(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon PLM modem configuration schema."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    await ws_client.send_json({ID: 2, TYPE: "insteon/config/get_modem_schema"})
    msg = await ws_client.receive_json()
    result = msg["result"][0]

    assert result["default"] == MOCK_DEVICE
    assert result["name"] == "device"
    assert result["required"]


async def test_get_modem_schema_hub(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon PLM modem configuration schema."""

    ws_client, devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
        config_data={**MOCK_USER_INPUT_HUB_V2, CONF_HUB_VERSION: 2},
    )
    await ws_client.send_json({ID: 2, TYPE: "insteon/config/get_modem_schema"})
    msg = await ws_client.receive_json()
    result = msg["result"][0]

    assert result["default"] == MOCK_HOSTNAME
    assert result["name"] == "host"
    assert result["required"]


async def test_update_modem_config_plm(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon PLM modem configuration schema."""

    ws_client, mock_devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
    )
    with (
        patch(
            "homeassistant.components.insteon.api.config.async_connect",
            new=mock_successful_connection,
        ),
        patch("homeassistant.components.insteon.api.config.devices", mock_devices),
        patch("homeassistant.components.insteon.api.config.async_close"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/config/update_modem_config",
                "config": MOCK_USER_INPUT_PLM,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

        assert result["status"] == "success"


async def test_update_modem_config_hub_v2(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon HubV2 modem configuration schema."""

    ws_client, mock_devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
        config_data={**MOCK_USER_INPUT_HUB_V2, CONF_HUB_VERSION: 2},
        config_options={"dev_path": "/some/path"},
    )
    with (
        patch(
            "homeassistant.components.insteon.api.config.async_connect",
            new=mock_successful_connection,
        ),
        patch("homeassistant.components.insteon.api.config.devices", mock_devices),
        patch("homeassistant.components.insteon.api.config.async_close"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/config/update_modem_config",
                "config": MOCK_USER_INPUT_HUB_V2,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

        assert result["status"] == "success"


async def test_update_modem_config_hub_v1(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the Insteon HubV1 modem configuration schema."""

    ws_client, mock_devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
        config_data={**MOCK_USER_INPUT_HUB_V1, CONF_HUB_VERSION: 1},
    )
    with (
        patch(
            "homeassistant.components.insteon.api.config.async_connect",
            new=mock_successful_connection,
        ),
        patch("homeassistant.components.insteon.api.config.devices", mock_devices),
        patch("homeassistant.components.insteon.api.config.async_close"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/config/update_modem_config",
                "config": MOCK_USER_INPUT_HUB_V1,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

        assert result["status"] == "success"


async def test_update_modem_config_bad(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updating the Insteon modem configuration with bad connection information."""

    ws_client, mock_devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
    )
    with (
        patch(
            "homeassistant.components.insteon.api.config.async_connect",
            new=mock_failed_connection,
        ),
        patch("homeassistant.components.insteon.api.config.devices", mock_devices),
        patch("homeassistant.components.insteon.api.config.async_close"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/config/update_modem_config",
                "config": MOCK_USER_INPUT_PLM,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["error"]
        assert result["code"] == "connection_failed"


async def test_update_modem_config_bad_reconnect(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updating the Insteon modem configuration with bad connection information so reconnect to old."""

    ws_client, mock_devices, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
    )
    with (
        patch(
            "homeassistant.components.insteon.api.config.async_connect",
            new=mock_failed_connection,
        ),
        patch("homeassistant.components.insteon.api.config.devices", mock_devices),
        patch("homeassistant.components.insteon.api.config.async_close"),
    ):
        mock_devices.modem.protocol = MockProtocol()
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/config/update_modem_config",
                "config": MOCK_USER_INPUT_PLM,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["error"]
        assert result["code"] == "connection_failed"


async def test_add_device_override(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a device configuration override."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    override = {
        "address": "99.99.99",
        "cat": "0x01",
        "subcat": "0x03",
    }
    await ws_client.send_json(
        {ID: 2, TYPE: "insteon/config/device_override/add", "override": override}
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_OVERRIDE]) == 1
    assert config_entry.options[CONF_OVERRIDE][0]["address"] == "99.99.99"


async def test_add_device_override_duplicate(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a duplicate device configuration override."""

    override = {
        "address": "99.99.99",
        "cat": "0x01",
        "subcat": "0x03",
    }

    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options={CONF_OVERRIDE: [override]}
    )
    await ws_client.send_json(
        {ID: 2, TYPE: "insteon/config/device_override/add", "override": override}
    )
    msg = await ws_client.receive_json()
    assert msg["error"]


async def test_remove_device_override(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a device configuration override."""

    override = {
        "address": "99.99.99",
        "cat": "0x01",
        "subcat": "0x03",
    }
    overrides = [
        override,
        {
            "address": "88.88.88",
            "cat": "0x02",
            "subcat": "0x05",
        },
    ]

    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options={CONF_OVERRIDE: overrides}
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/config/device_override/remove",
            "device_address": "99.99.99",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_OVERRIDE]) == 1
    assert config_entry.options[CONF_OVERRIDE][0]["address"] == "88.88.88"


async def test_add_device_override_with_x10(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a device configuration override when X10 configuration exists."""

    x10_device = {"housecode": "a", "unitcode": 1, "platform": "switch"}
    ws_client, _, _, _ = await async_mock_setup(
        hass, hass_ws_client, config_options={CONF_X10: [x10_device]}
    )
    override = {
        "address": "99.99.99",
        "cat": "0x01",
        "subcat": "0x03",
    }
    await ws_client.send_json(
        {ID: 2, TYPE: "insteon/config/device_override/add", "override": override}
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_X10]) == 1


async def test_remove_device_override_with_x10(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a device configuration override when X10 configuration exists."""

    override = {
        "address": "99.99.99",
        "cat": "0x01",
        "subcat": "0x03",
    }
    overrides = [
        override,
        {
            "address": "88.88.88",
            "cat": "0x02",
            "subcat": "0x05",
        },
    ]
    x10_device = {"housecode": "a", "unitcode": 1, "platform": "switch"}

    ws_client, _, _, _ = await async_mock_setup(
        hass,
        hass_ws_client,
        config_options={CONF_OVERRIDE: overrides, CONF_X10: [x10_device]},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/config/device_override/remove",
            "device_address": "99.99.99",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert len(config_entry.options[CONF_X10]) == 1


async def test_remove_device_override_no_overrides(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a device override when no overrides are configured."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "insteon/config/device_override/remove",
            "device_address": "99.99.99",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    config_entry = hass.config_entries.async_get_entry("abcde12345")
    assert not config_entry.options.get(CONF_OVERRIDE)


async def test_get_broken_links(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting broken ALDB links."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    devices = MockDevices()
    await devices.async_load()
    aldb_data = json.loads(load_fixture("insteon/aldb_data.json"))
    devices.fill_aldb("33.33.33", aldb_data)
    await asyncio.sleep(1)
    with patch.object(insteon.api.config, "devices", devices):
        await ws_client.send_json({ID: 2, TYPE: "insteon/config/get_broken_links"})
        msg = await ws_client.receive_json()
        assert msg["success"]

        assert len(msg["result"]) == 5


async def test_get_unknown_devices(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting unknown Insteon devices."""

    ws_client, _, _, _ = await async_mock_setup(hass, hass_ws_client)
    devices = MockDevices()
    await devices.async_load()
    aldb_data = {
        "4095": {
            "memory": 4095,
            "in_use": True,
            "controller": False,
            "high_water_mark": False,
            "bit5": True,
            "bit4": False,
            "group": 0,
            "target": "FFFFFF",
            "data1": 0,
            "data2": 0,
            "data3": 0,
        },
    }
    devices.fill_aldb("33.33.33", aldb_data)
    with patch.object(insteon.api.config, "devices", devices):
        await ws_client.send_json({ID: 2, TYPE: "insteon/config/get_unknown_devices"})
        msg = await ws_client.receive_json()
        assert msg["success"]

        assert len(msg["result"]) == 1
        await asyncio.sleep(0.1)
