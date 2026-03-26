"""SNMP tests."""

from unittest.mock import AsyncMock, Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD

from homeassistant.components import snmp
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_get_snmp_engine(hass: HomeAssistant) -> None:
    """Test async_get_snmp_engine."""
    engine = await snmp.async_get_snmp_engine(hass)
    assert isinstance(engine, SnmpEngine)
    engine2 = await snmp.async_get_snmp_engine(hass)
    assert engine is engine2
    with patch.object(LCD, "unconfigure") as mock_unconfigure:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    assert mock_unconfigure.called


async def test_async_setup_entry_custom_port(hass: HomeAssistant) -> None:
    """Test async_setup_entry with a custom port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1161,
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value=Mock(),
        ) as mock_create,
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(None, None, None, []),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify that UdpTransportTarget.create was called with the custom port
    mock_create.assert_called_once()
    args, _ = mock_create.call_args
    assert args[0] == ("1.2.3.4", 1161)


async def test_async_setup_entry_v3_no_keys(hass: HomeAssistant) -> None:
    """Test async_setup_entry with SNMP v3 and no auth/priv keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "3",
            "username": "test-user",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(None, None, None, [("oid1", "descr"), ("oid2", "sys_name")]),
        ),
        patch(
            "homeassistant.components.snmp.SnmpUpdateCoordinator",
        ) as mock_coord,
    ):
        mock_inst = mock_coord.return_value
        mock_inst.sys_name = "sys_name"
        mock_inst.async_config_entry_first_refresh = AsyncMock()
        mock_inst.manufacturer = "man"
        mock_inst.model = "mod"
        mock_inst.sw_version = "1.0"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.title == "sys_name"


async def test_async_setup_entry_ipv6_fallback(hass: HomeAssistant) -> None:
    """Test async_setup_entry with IPv6 fallback."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            return_value=Mock(),
        ) as mock_create6,
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(None, None, None, []),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_create6.assert_called_once()


async def test_async_setup_entry_fail_all(hass: HomeAssistant) -> None:
    """Test async_setup_entry failing both IPv4 and IPv6."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            side_effect=PySnmpError,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_async_setup_entry_unexpected_error(hass: HomeAssistant) -> None:
    """Test async_setup_entry with an unexpected error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=Exception,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_async_setup_entry_refresh_fail(hass: HomeAssistant) -> None:
    """Test async_setup_entry with refresh failure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.SnmpUpdateCoordinator.async_config_entry_first_refresh",
            side_effect=PySnmpError,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
