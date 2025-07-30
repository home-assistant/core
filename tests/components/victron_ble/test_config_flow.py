"""Test the Victron Bluetooth Low Energy config flow."""

from unittest.mock import AsyncMock

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.victron_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .fixtures import (
    NOT_VICTRON_SERVICE_INFO,
    VICTRON_INVERTER_SERVICE_INFO,
    VICTRON_TEST_WRONG_TOKEN,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Mock bluetooth for all tests in this module."""


async def test_async_step_bluetooth_valid_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "access_token"

    # test valid access token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: VICTRON_VEBUS_TOKEN},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == VICTRON_VEBUS_SERVICE_INFO.name
    flow_result = result.get("result")
    assert flow_result is not None
    assert flow_result.unique_id == VICTRON_VEBUS_SERVICE_INFO.address


@pytest.mark.parametrize(
    ("source", "service_info", "expected_reason", "test_description"),
    [
        (
            config_entries.SOURCE_BLUETOOTH,
            NOT_VICTRON_SERVICE_INFO,
            "not_supported",
            "not a victron device",
        ),
        (
            config_entries.SOURCE_BLUETOOTH,
            VICTRON_INVERTER_SERVICE_INFO,
            "not_supported",
            "victron device unsupported by library",
        ),
        (
            config_entries.SOURCE_USER,
            None,
            "no_devices_found",
            "no devices found",
        ),
    ],
)
async def test_abort_scenarios(
    hass: HomeAssistant,
    source: str,
    service_info: BluetoothServiceInfo | None,
    expected_reason: str,
    test_description: str,
) -> None:
    """Test flows that result in abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=service_info,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_reason


async def test_async_step_user_with_devices_found(
    hass: HomeAssistant, mock_discovered_service_info: AsyncMock
) -> None:
    """Test setup from service info cache with devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: VICTRON_VEBUS_SERVICE_INFO.address},
    )
    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "access_token"

    # test invalid access token (valid already tested above)
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={CONF_ACCESS_TOKEN: VICTRON_TEST_WRONG_TOKEN}
    )
    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "invalid_access_token"


async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Test abort when the device gets added via another flow between steps."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_config_entry.add_to_hass(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": VICTRON_VEBUS_SERVICE_INFO.address},
    )
    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Test setup from service info cache with devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(
    hass: HomeAssistant, mock_config_entry_added_to_hass: MockConfigEntry
) -> None:
    """Test we can't start a flow if there is already a config entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "access_token"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_in_progress"
