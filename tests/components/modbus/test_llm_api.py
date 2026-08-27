"""Test the Modbus LLM API."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusTcpParams
import pytest
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit, async_get_unit
from homeassistant.components.modbus.llm_api import API_ID
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

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


def _context(hass: HomeAssistant) -> llm.LLMContext:
    """Build a context for calling the API."""
    return llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant=None,
        device_id=None,
    )


async def _instance(hass: HomeAssistant) -> llm.APIInstance:
    """Return the API instance."""
    return await llm.async_get_api(hass, API_ID, _context(hass))


async def _hold_a_unit(
    hass: HomeAssistant, consumer: ConsumerFactory, unit_id: int = 1
) -> MockConfigEntry:
    """Open one connection by asking for a unit on it."""
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="device.local", port=502), unit_id)
    return entry


async def test_the_api_is_registered(hass: HomeAssistant) -> None:
    """Setting the component up offers the API to assistants."""
    assert await async_setup_component(hass, "modbus", {})

    assert API_ID in [api.id for api in llm.async_get_apis(hass)]


async def test_listing_names_the_open_connections(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """The tool reports what is connected, and which units are in use on it."""
    assert await async_setup_component(hass, "modbus", {})
    first = await _hold_a_unit(hass, consumer, 1)
    second = await _hold_a_unit(hass, consumer, 2)

    result = await (await _instance(hass)).async_call_tool(
        llm.ToolInput(tool_name="list_modbus_devices", tool_args={})
    )

    assert result["devices"] == [
        {
            "endpoint": ["tcp", "device.local", 502],
            "connected": False,
            "units": {first.entry_id: [1], second.entry_id: [2]},
        }
    ]


async def test_reading_goes_over_the_open_connection(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """A read reaches the device through the connection already held."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    with patch("modbus_connection.tmodbus.ModbusConnection.for_unit") as for_unit:
        for_unit.return_value.read_holding_registers = AsyncMock(return_value=[1, 2, 3])
        result = await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block",
                tool_args={
                    "endpoint": ["tcp", "device.local", 502],
                    "unit_id": 1,
                    "address": 40000,
                    "count": 3,
                    "table": "holding",
                },
            )
        )

    assert result == {
        "address": 40000,
        "table": "holding",
        "values": [1, 2, 3],
    }


async def test_reading_an_unknown_device_is_refused(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """The model may only read a device Home Assistant already talks to."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    with pytest.raises(HomeAssistantError, match="holds no unit"):
        await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block",
                tool_args={
                    "endpoint": ["tcp", "elsewhere.local", 502],
                    "unit_id": 1,
                    "address": 0,
                    "count": 1,
                },
            )
        )


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ({"unit_id": 0}, "0 is a broadcast, which has no reply to read"),
        ({"unit_id": 248}, "past the last addressable unit"),
        ({"address": -1}, "before the first register"),
        ({"address": 70000}, "past the last register"),
        ({"count": 0}, "a block of nothing"),
        ({"count": 126}, "more registers than one request may carry"),
        ({"address": 65500, "count": 100}, "a block running off the end"),
    ],
)
async def test_a_block_outside_the_protocol_is_refused(
    hass: HomeAssistant,
    consumer: ConsumerFactory,
    args: dict[str, int],
    why: str,
) -> None:
    """The schema rejects it here, rather than the transport rejecting it later."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    tool_args = {
        "endpoint": ["tcp", "device.local", 502],
        "unit_id": 1,
        "address": 0,
        "count": 1,
    } | args

    with pytest.raises(vol.Invalid):
        await (await _instance(hass)).async_call_tool(
            llm.ToolInput(tool_name="read_modbus_block", tool_args=tool_args)
        )


@pytest.mark.parametrize(
    ("table", "reader", "answer"),
    [
        ("holding", "read_holding_registers", [1, 2]),
        ("input", "read_input_registers", [3, 4]),
        ("coil", "read_coils", [True, False]),
        ("discrete_input", "read_discrete_inputs", [False, True]),
    ],
)
async def test_each_table_is_read_from_its_own_space(
    hass: HomeAssistant,
    consumer: ConsumerFactory,
    table: str,
    reader: str,
    answer: list[int] | list[bool],
) -> None:
    """The four tables are separate, so each goes out on its own function."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    with patch("modbus_connection.tmodbus.ModbusConnection.for_unit") as for_unit:
        setattr(for_unit.return_value, reader, AsyncMock(return_value=answer))
        result = await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block",
                tool_args={
                    "endpoint": ["tcp", "device.local", 502],
                    "unit_id": 1,
                    "address": 0,
                    "count": 2,
                    "table": table,
                },
            )
        )

    assert result == {"address": 0, "table": table, "values": answer}


@pytest.mark.parametrize(
    ("table", "count"),
    [
        ("holding", 126),
        ("input", 126),
        ("coil", 2001),
        ("discrete_input", 2001),
    ],
)
async def test_a_table_refuses_more_than_one_request_carries(
    hass: HomeAssistant, consumer: ConsumerFactory, table: str, count: int
) -> None:
    """Registers cap at 125 and single-bit tables at 2000."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    with pytest.raises(vol.Invalid):
        await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block",
                tool_args={
                    "endpoint": ["tcp", "device.local", 502],
                    "unit_id": 1,
                    "address": 0,
                    "count": count,
                    "table": table,
                },
            )
        )


async def test_a_bit_table_may_read_more_than_a_register_table(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """1000 coils is one request; 1000 registers is not."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer)

    args = {
        "endpoint": ["tcp", "device.local", 502],
        "unit_id": 1,
        "address": 0,
        "count": 1000,
    }

    with patch("modbus_connection.tmodbus.ModbusConnection.for_unit") as for_unit:
        for_unit.return_value.read_coils = AsyncMock(return_value=[True] * 1000)
        result = await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block", tool_args=args | {"table": "coil"}
            )
        )
    assert len(result["values"]) == 1000

    with pytest.raises(vol.Invalid):
        await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block", tool_args=args | {"table": "holding"}
            )
        )


async def test_reading_a_unit_nobody_holds_is_refused(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """The endpoint alone is not the boundary: a gateway carries other devices."""
    assert await async_setup_component(hass, "modbus", {})
    await _hold_a_unit(hass, consumer, 1)

    with pytest.raises(HomeAssistantError, match="holds no unit 7"):
        await (await _instance(hass)).async_call_tool(
            llm.ToolInput(
                tool_name="read_modbus_block",
                tool_args={
                    "endpoint": ["tcp", "device.local", 502],
                    "unit_id": 7,  # on the same bus, but nobody asked for it
                    "address": 0,
                    "count": 1,
                },
            )
        )


async def test_a_device_only_being_probed_is_invisible(hass: HomeAssistant) -> None:
    """A config flow's hold is a device nobody has accepted yet."""
    assert await async_setup_component(hass, "modbus", {})
    params = ModbusTcpParams(host="probing.local", port=502)

    async with async_get_temporary_unit(hass, params, 1):
        listed = await (await _instance(hass)).async_call_tool(
            llm.ToolInput(tool_name="list_modbus_devices", tool_args={})
        )

        assert listed["devices"] == []

        with pytest.raises(HomeAssistantError, match="holds no unit"):
            await (await _instance(hass)).async_call_tool(
                llm.ToolInput(
                    tool_name="read_modbus_block",
                    tool_args={
                        "endpoint": ["tcp", "probing.local", 502],
                        "unit_id": 1,
                        "address": 0,
                        "count": 1,
                    },
                )
            )
