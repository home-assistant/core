"""SNMP tests."""

from unittest.mock import Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant.components import snmp
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr

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
        title="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            "baseoid": "1.3.6.1.2.1.1",
            "version": "3",
            "username": "test-user",
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
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(None, None, None, [("oid1", "descr"), ("oid2", "sys_name")]),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


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

    with patch(
        "homeassistant.components.snmp.util.UdpTransportTarget.create",
        side_effect=RuntimeError("Something unexpected"),
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


async def test_async_setup_entry_wrong_value_error(hass: HomeAssistant) -> None:
    """Test async_setup_entry with WrongValueError."""
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
            side_effect=ConfigEntryAuthFailed,
        ),
        patch("homeassistant.config_entries.ConfigEntry.async_start_reauth"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
def mock_coordinator_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry for coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_walk_error_makes_entry_unavailable(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that a PySnmpError during walk makes the coordinator report failure."""

    async def mock_walk_error(*args, **kwargs):
        raise PySnmpError("Network unreachable")
        yield  # pylint: disable=unreachable

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_error,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_walk_errstatus(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that errstatus during walk causes UpdateFailed."""
    mock_err_status = Mock()
    mock_err_status.prettyPrint.return_value = "noSuchName"

    async def mock_walk(*args, **kwargs):
        yield None, mock_err_status, 1, [("oid", "val")]

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_host_info_populates_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that host info is fetched and populates the device registry."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Cisco IOS 15.1"), ("oid2", "router01")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_coordinator_entry.entry_id), mock_coordinator_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Cisco"
    assert device.model == "IOS 15.1"
    assert device.name == "router01"


async def test_host_info_no_space_in_descr(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test host info when sysDescr has no spaces."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "SingleWordDescr"), ("oid2", "myhost")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_coordinator_entry.entry_id), mock_coordinator_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer is None
    assert device.model == "SingleWordDescr"


async def test_host_info_pysnmp_error_sets_empty_model(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that a PySnmpError during host info fetch prevents re-fetching."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            side_effect=PySnmpError("Connection timed out"),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_coordinator_entry.entry_id), mock_coordinator_entry.entry_id
    )
    assert device is not None
    assert device.model == ""


async def test_host_info_errstatus_sets_generic_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that get_cmd with errindication/errstatus sets a generic model name."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=("some error indication", None, None, []),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_coordinator_entry.entry_id), mock_coordinator_entry.entry_id
    )
    assert device is not None
    assert device.model == "SNMP Server"


async def test_host_info_auth_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that WrongValueError during host info get_cmd triggers reauth."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            side_effect=WrongValueError,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_host_info_request_args_wrong_value_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test WrongValueError raised by _async_ensure_request_args during host info."""
    with (
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=WrongValueError,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_update_data_request_args_wrong_value_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test WrongValueError raised by _async_ensure_request_args during update.

    Host info succeeds via the PySnmpError fallback (sets model=''), then
    _async_ensure_request_args is called again in _async_update_data and raises
    WrongValueError, triggering ConfigEntryAuthFailed.
    """
    call_count = 0

    async def mock_create_request_args_side(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PySnmpError("First call fails")
        raise WrongValueError

    with (
        patch(
            "homeassistant.components.snmp.coordinator.create_auth_data",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=mock_create_request_args_side,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_update_data_request_args_pysnmp_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test PySnmpError raised by _async_ensure_request_args during update.

    Host info succeeds via the PySnmpError fallback (sets model=''), then
    _async_ensure_request_args is called again in _async_update_data and raises
    PySnmpError, triggering UpdateFailed.
    """

    async def mock_create_request_args_fail(*args, **kwargs):
        raise PySnmpError("Always fails")

    with (
        patch(
            "homeassistant.components.snmp.coordinator.create_auth_data",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=mock_create_request_args_fail,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_walk_auth_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that WrongValueError during walk triggers reauth."""
    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=WrongValueError,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()
