"""Test the Sunsynk integration setup."""

from unittest.mock import AsyncMock

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunsynk.const import DOMAIN, TYPE_CLOUD
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import MODBUS_SERIAL_NUMBER, PASSWORD, USER_ID, USERNAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("method", "exception", "result"),
    [
        ("get_inverters", SunsynkConnectionError, ConfigEntryState.SETUP_RETRY),
        ("get_inverters", SunsynkAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (
            "get_inverter_realtime_grid",
            SunsynkConnectionError,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_inverter_realtime_grid",
            SunsynkAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    exception: Exception,
    result: ConfigEntryState,
) -> None:
    """Test the config entry retries when the API cannot be reached."""
    getattr(mock_sunsynk_client, method).side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is result


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a device is created for each inverter."""
    await setup_integration(hass, mock_config_entry)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 3
    assert devices == snapshot


@pytest.mark.usefixtures("mock_get_unit")
async def test_load_unload_modbus_entry(
    hass: HomeAssistant, mock_modbus_config_entry: MockConfigEntry
) -> None:
    """Test a Modbus config entry loads and unloads."""
    await setup_integration(hass, mock_modbus_config_entry)
    assert mock_modbus_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_modbus_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_modbus_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_get_unit")
async def test_modbus_setup_retry(
    hass: HomeAssistant,
    mock_modbus_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a Modbus config entry tries again when the inverter does not reply."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("no reply"))
    await setup_integration(hass, mock_modbus_config_entry)
    assert mock_modbus_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_get_unit")
async def test_modbus_wrong_inverter(
    hass: HomeAssistant,
    mock_modbus_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a Modbus config entry does not load the data of a different inverter."""
    # The serial number 2209876543, two ASCII characters in each register.
    mock_modbus_unit.load_raw(
        {"holding": {3: 0x3232, 4: 0x3039, 5: 0x3837, 6: 0x3635, 7: 0x3433}}
    )
    await setup_integration(hass, mock_modbus_config_entry)
    assert mock_modbus_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_modbus_config_entry.reason == (
        "The inverter at this address has the serial number 2209876543. The "
        "expected serial number is 2201234567. Make sure that the host and the "
        "unit ID are correct"
    )


@pytest.mark.usefixtures("mock_get_unit")
async def test_modbus_devices(
    hass: HomeAssistant,
    mock_modbus_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test an inverter that uses Modbus gets an inverter and a battery device."""
    await setup_integration(hass, mock_modbus_config_entry)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_modbus_config_entry.entry_id
    )
    assert len(devices) == 2
    assert devices == snapshot

    entry_id = mock_modbus_config_entry.entry_id
    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, MODBUS_SERIAL_NUMBER), entry_id
    )
    battery = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MODBUS_SERIAL_NUMBER}_battery"), entry_id
    )
    assert inverter is not None
    assert battery is not None
    assert battery.via_device_id == inverter.id


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_migrate_cloud_entry(hass: HomeAssistant) -> None:
    """Test an entry from before Modbus support is marked as a cloud entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=USER_ID,
        minor_version=1,
    )
    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data == {
        CONF_TYPE: TYPE_CLOUD,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }
