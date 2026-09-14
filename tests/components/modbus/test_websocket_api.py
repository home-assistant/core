"""Test the Modbus websocket API."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
import pytest

from homeassistant import config as hass_config
from homeassistant.components.modbus import async_get_unit
from homeassistant.components.modbus.const import DATA_MODBUS_HUBS
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    get_fixture_path,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator

type ConsumerFactory = Callable[[], MockConfigEntry]

YAML_HUB_NAME = "yaml_hub"

# The host is given in mixed case, as a shared connection folds the one it is
# keyed by to lower case
TCP_TRANSPORT = {"type": "tcp", "host": "Device.Local", "port": 502}

SERIAL_TRANSPORT = {
    "type": "serial",
    "port": "/dev/ttyUSB0",
    "baudrate": 9600,
    "bytesize": 8,
    "method": "rtu",
    "parity": "E",
    "stopbits": 1,
}


def yaml_hub(transport: dict[str, Any]) -> dict[str, Any]:
    """Return a hub config on *transport*, with sensors on three units."""
    return {
        "name": YAML_HUB_NAME,
        "sensors": [
            {"name": "on unit 3", "address": 10, "slave": 3},
            {"name": "on unit 2", "address": 11, "device_address": 2},
            {"name": "on the default unit", "address": 12},
        ],
        **transport,
    }


class MockFlow(ConfigFlow):
    """A config flow for the integration standing in for a consumer."""


@pytest.fixture(name="consumer")
def consumer_fixture(hass: HomeAssistant) -> Generator[ConsumerFactory]:
    """Return a factory for config entries that can be set up and unloaded."""
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "test.config_flow")

    def _consumer() -> MockConfigEntry:
        entry = MockConfigEntry(domain="test")
        entry.add_to_hass(hass)
        return entry

    with mock_config_flow("test", MockFlow):
        yield _consumer


async def test_list_connections(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    consumer: ConsumerFactory,
) -> None:
    """Two entries on one device are one connection naming both."""
    assert await async_setup_component(hass, "modbus", {})

    first = consumer()
    await hass.config_entries.async_setup(first.entry_id)
    second = consumer()
    await hass.config_entries.async_setup(second.entry_id)

    params = ModbusTcpParams(host="device.local", port=502)
    async_get_unit(hass, first, params, 1)
    async_get_unit(hass, second, params, 2)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result == {
        "connections": [
            {
                "endpoint": ["tcp", "device.local", 502],
                "connected": False,
                "source": "config_entry",
                "units": {first.entry_id: [1], second.entry_id: [2]},
            }
        ]
    }


async def test_a_connection_that_is_up_reports_itself_connected(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    consumer: ConsumerFactory,
) -> None:
    """The reported state follows the connection, rather than being fixed."""
    assert await async_setup_component(hass, "modbus", {})

    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="device.local", port=502), 1)

    client = await hass_ws_client(hass)
    with patch.object(ModbusConnection, "connected", True):
        await client.send_json_auto_id({"type": "modbus/connections/list"})
        result = (await client.receive_json())["result"]

    assert result == {
        "connections": [
            {
                "endpoint": ["tcp", "device.local", 502],
                "connected": True,
                "source": "config_entry",
                "units": {entry.entry_id: [1]},
            }
        ]
    }


async def test_listing_the_connections_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """The endpoint names devices and config entries, so admins only."""
    assert await async_setup_component(hass, "modbus", {})

    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_unloading_an_entry_drops_it_from_the_listing(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    consumer: ConsumerFactory,
) -> None:
    """The connection stays while somebody else holds a unit on it."""
    assert await async_setup_component(hass, "modbus", {})

    first = consumer()
    await hass.config_entries.async_setup(first.entry_id)
    second = consumer()
    await hass.config_entries.async_setup(second.entry_id)

    params = ModbusTcpParams(host="device.local", port=502)
    async_get_unit(hass, first, params, 1)
    async_get_unit(hass, second, params, 2)

    await hass.config_entries.async_unload(first.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert len(result["connections"]) == 1
    assert result["connections"][0]["units"] == {second.entry_id: [2]}


async def test_no_connections_when_nobody_asked(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Nothing is opened until an integration asks for a unit."""
    assert await async_setup_component(hass, "modbus", {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})

    assert (await client.receive_json())["result"] == {"connections": []}


async def test_one_entry_holding_two_units(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    consumer: ConsumerFactory,
) -> None:
    """An entry with two devices on one link reports both units."""
    assert await async_setup_component(hass, "modbus", {})

    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)

    params = ModbusTcpParams(host="device.local", port=502)
    async_get_unit(hass, entry, params, 1)
    async_get_unit(hass, entry, params, 2)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result["connections"][0]["units"] == {entry.entry_id: [1, 2]}


async def test_a_yaml_hub_is_listed_with_the_units_its_entities_address(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_pymodbus: AsyncMock,
) -> None:
    """A hub is flagged as YAML and keyed by its name, having no config entry."""
    mock_pymodbus.connected = True
    assert await async_setup_component(
        hass, "modbus", {"modbus": [yaml_hub(TCP_TRANSPORT)]}
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result == {
        "connections": [
            {
                "endpoint": ["tcp", "device.local", 502],
                "connected": True,
                "source": "yaml",
                "units": {YAML_HUB_NAME: [1, 2, 3]},
            }
        ]
    }


async def test_a_closed_yaml_hub_reports_itself_not_connected(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_pymodbus: AsyncMock,
) -> None:
    """The stop action drops the client, which is no longer a link."""
    mock_pymodbus.connected = True
    assert await async_setup_component(
        hass, "modbus", {"modbus": [yaml_hub(TCP_TRANSPORT)]}
    )
    await hass.data[DATA_MODBUS_HUBS][YAML_HUB_NAME].async_close()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result["connections"][0]["connected"] is False


async def test_a_yaml_hub_is_listed_beside_a_connection_to_the_same_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    consumer: ConsumerFactory,
    mock_pymodbus: AsyncMock,
) -> None:
    """A hub is a link of its own, so it is never folded into a shared one."""
    mock_pymodbus.connected = False
    assert await async_setup_component(
        hass, "modbus", {"modbus": [yaml_hub(TCP_TRANSPORT)]}
    )

    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="device.local", port=502), 7)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result["connections"] == [
        {
            "endpoint": ["tcp", "device.local", 502],
            "connected": False,
            "source": "config_entry",
            "units": {entry.entry_id: [7]},
        },
        {
            "endpoint": ["tcp", "device.local", 502],
            "connected": False,
            "source": "yaml",
            "units": {YAML_HUB_NAME: [1, 2, 3]},
        },
    ]


@pytest.mark.parametrize(
    ("transport", "endpoint"),
    [
        pytest.param(TCP_TRANSPORT, ["tcp", "device.local", 502], id="tcp"),
        pytest.param(
            {**TCP_TRANSPORT, "type": "rtuovertcp"},
            ["tcp", "device.local", 502],
            id="rtuovertcp",
        ),
        pytest.param(
            {**TCP_TRANSPORT, "type": "udp"}, ["udp", "device.local", 502], id="udp"
        ),
        pytest.param(SERIAL_TRANSPORT, ["serial", "/dev/ttyUSB0"], id="serial"),
    ],
)
async def test_the_endpoint_of_a_yaml_hub_follows_its_transport(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_pymodbus: AsyncMock,
    transport: dict[str, Any],
    endpoint: list[str | int],
) -> None:
    """A hub is keyed by the device it addresses, as a shared connection is.

    An RTU-over-TCP hub keys as TCP: the framing differs, the device does not.
    """
    mock_pymodbus.connected = True
    assert await async_setup_component(
        hass, "modbus", {"modbus": [yaml_hub(transport)]}
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    result = (await client.receive_json())["result"]

    assert result["connections"][0]["endpoint"] == endpoint


@pytest.mark.parametrize(
    "fixture",
    [
        pytest.param("configuration_empty.yaml", id="modbus gone from yaml"),
        pytest.param("configuration_no_entities.yaml", id="hub without entities"),
    ],
)
async def test_a_yaml_hub_a_reload_leaves_behind_is_not_listed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_pymodbus: AsyncMock,
    fixture: str,
) -> None:
    """A reload that sets no hub up again leaves no connection behind.

    The reload closes the hubs before reading the new config, so one it does
    not set up again is a link to a device nothing talks to.
    """
    mock_pymodbus.connected = True
    assert await async_setup_component(
        hass, "modbus", {"modbus": [yaml_hub(TCP_TRANSPORT)]}
    )

    yaml_path = get_fixture_path(fixture, "modbus")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call("modbus", SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})

    assert (await client.receive_json())["result"] == {"connections": []}
