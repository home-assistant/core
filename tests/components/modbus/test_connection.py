"""Test handing out Modbus units over shared connections."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
import pytest

from homeassistant.components.modbus.connection import (
    DATA_MODBUS_CONNECTIONS,
    async_get_temporary_unit,
    async_get_unit,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


async def test_equal_credentials_share_one_connection(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """Two consumers of one device queue behind one link, not two.

    A device answering one conversation cannot be asked a second question
    halfway through it.
    """
    one = consumer()
    await hass.config_entries.async_setup(one.entry_id)
    two = consumer()
    await hass.config_entries.async_setup(two.entry_id)

    async_get_unit(hass, one, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    async_get_unit(hass, two, ModbusTcpParams(host="1.2.3.4", port=502), 2)

    [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.consumers == 2


async def test_different_credentials_get_their_own_connection(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """A different host, port or transport is a different device."""
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)

    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=503), 1)
    async_get_unit(hass, entry, ModbusSerialParams(device="/dev/ttyUSB0"), 1)

    assert len(hass.data[DATA_MODBUS_CONNECTIONS]) == 3


async def test_the_same_device_reached_by_a_different_name_still_shares(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """Hostnames are case-insensitive, so the case must not split the link."""
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)

    async_get_unit(hass, entry, ModbusTcpParams(host="Device.local", port=502), 1)
    async_get_unit(hass, entry, ModbusTcpParams(host="device.local", port=502), 2)

    assert len(hass.data[DATA_MODBUS_CONNECTIONS]) == 1


async def test_one_device_cannot_be_used_with_two_link_settings(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """One connection can only be framed one way, so the clash has to be said.

    Silently keeping the first would leave the second consumer reading a device
    over settings it did not ask for.
    """
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)

    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)

    with pytest.raises(HomeAssistantError, match="different link settings"):
        async_get_unit(
            hass, entry, ModbusTcpParams(host="1.2.3.4", port=502, framer="rtu"), 2
        )


async def test_the_last_consumer_closes_the_connection(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """A connection lives exactly as long as somebody holds a unit on it."""
    one = consumer()
    await hass.config_entries.async_setup(one.entry_id)
    two = consumer()
    await hass.config_entries.async_setup(two.entry_id)

    async_get_unit(hass, one, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    async_get_unit(hass, two, ModbusTcpParams(host="1.2.3.4", port=502), 2)
    [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()

    with patch.object(shared.connection, "close") as close:
        await hass.config_entries.async_unload(one.entry_id)
        await hass.async_block_till_done()

        # One consumer left, so the link it is still using stays up.
        assert not close.called
        assert hass.data[DATA_MODBUS_CONNECTIONS]

        await hass.config_entries.async_unload(two.entry_id)
        await hass.async_block_till_done()

    assert close.called
    assert not hass.data[DATA_MODBUS_CONNECTIONS]


async def test_one_entry_holding_twice_releases_twice(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """An entry with two devices on one link holds it twice.

    Counting entries rather than units would close the link under the second
    device the moment the entry unloaded once.
    """
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)

    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 2)
    [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.consumers == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data[DATA_MODBUS_CONNECTIONS]


async def test_reloading_an_entry_reopens_the_connection(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """Nothing is held across a reload, so the entry gets a fresh connection.

    There is no grace period; that is what lets a stale connection be recovered.
    """
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    [first] = hass.data[DATA_MODBUS_CONNECTIONS].values()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data[DATA_MODBUS_CONNECTIONS]

    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)
    [second] = hass.data[DATA_MODBUS_CONNECTIONS].values()

    assert second.connection is not first.connection


async def test_a_temporary_unit_closes_the_connection_on_exit(
    hass: HomeAssistant,
) -> None:
    """A config flow's hold ends with the context, not with a config entry."""
    with patch.object(ModbusConnection, "close") as close:
        async with async_get_temporary_unit(
            hass, ModbusTcpParams(host="1.2.3.4", port=502), 1
        ):
            [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()
            assert shared.consumers == 1

    assert close.called
    assert not hass.data[DATA_MODBUS_CONNECTIONS]


async def test_a_temporary_unit_releases_when_the_context_raises(
    hass: HomeAssistant,
) -> None:
    """A flow step failing must not leak the connection it probed over."""
    with patch.object(ModbusConnection, "close") as close, pytest.raises(ValueError):
        async with async_get_temporary_unit(
            hass, ModbusTcpParams(host="1.2.3.4", port=502), 1
        ):
            raise ValueError

    assert close.called
    assert not hass.data[DATA_MODBUS_CONNECTIONS]


async def test_a_temporary_unit_shares_a_connection_an_entry_holds(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """A flow probing a device an entry already talks to joins its connection.

    The connection outlives the flow because the entry still holds it.
    """
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    params = ModbusTcpParams(host="1.2.3.4", port=502)
    async_get_unit(hass, entry, params, 1)
    [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()

    async with async_get_temporary_unit(hass, params, 2):
        assert shared.consumers == 2

    assert shared.consumers == 1
    assert hass.data[DATA_MODBUS_CONNECTIONS]


async def test_a_temporary_unit_cannot_clash_with_held_link_settings(
    hass: HomeAssistant, consumer: ConsumerFactory
) -> None:
    """A flow gets told about a link settings clash when entering the context."""
    entry = consumer()
    await hass.config_entries.async_setup(entry.entry_id)
    async_get_unit(hass, entry, ModbusTcpParams(host="1.2.3.4", port=502), 1)

    with pytest.raises(HomeAssistantError, match="different link settings"):
        async with async_get_temporary_unit(
            hass, ModbusTcpParams(host="1.2.3.4", port=502, framer="rtu"), 2
        ):
            pass

    [shared] = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.consumers == 1
