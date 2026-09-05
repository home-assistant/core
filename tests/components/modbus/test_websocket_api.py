"""Test the Modbus websocket API."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock

from modbus_connection import ModbusTcpParams
import pytest

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator

type ConsumerFactory = Callable[[], MockConfigEntry]


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

    assert len(result["connections"]) == 1
    reported = result["connections"][0]
    assert reported["endpoint"] == ["tcp", "device.local", 502]
    assert reported["units"] == {first.entry_id: [1], second.entry_id: [2]}


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
