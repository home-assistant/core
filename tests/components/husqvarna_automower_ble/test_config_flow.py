"""Test the Husqvarna Bluetooth config flow."""

from unittest.mock import Mock, patch

from bleak import BleakError
import pytest

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    AUTOMOWER_MISSING_SERVICE_SERVICE_INFO,
    AUTOMOWER_SERVICE_INFO,
    AUTOMOWER_UNNAMED_SERVICE_INFO,
    AUTOMOWER_UNSUPPORTED_GROUP_SERVICE_INFO,
)

from tests.components.bluetooth import inject_bluetooth_service_info

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
def mock_random() -> Mock:
    """Mock random to generate predictable client id."""
    with patch(
        "homeassistant.components.husqvarna_automower_ble.config_flow.random"
    ) as mock_random:
        mock_random.randint.return_value = 1197489078
        yield mock_random


async def test_user_selection(hass: HomeAssistant) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, AUTOMOWER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: "00000000-0000-0000-0000-000000000001"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000001"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
        CONF_CLIENT_ID: 1197489078,
    }


async def test_no_devices(hass: HomeAssistant) -> None:
    """Test missing device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_MISSING_SERVICE_SERVICE_INFO)
    inject_bluetooth_service_info(hass, AUTOMOWER_UNSUPPORTED_GROUP_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_bluetooth(hass: HomeAssistant) -> None:
    """Test bluetooth device discovery."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "confirm"
    assert result["context"]["unique_id"] == "00000000-0000-0000-0000-000000000003"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000003"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
        CONF_CLIENT_ID: 1197489078,
    }


async def test_bluetooth_invalid(hass: HomeAssistant) -> None:
    """Test bluetooth device discovery with invalid data."""

    inject_bluetooth_service_info(hass, AUTOMOWER_UNSUPPORTED_GROUP_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=AUTOMOWER_UNSUPPORTED_GROUP_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_failed_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, AUTOMOWER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.connect.side_effect = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: "00000000-0000-0000-0000-000000000001"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000001"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
        CONF_CLIENT_ID: 1197489078,
    }


async def test_exception_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, AUTOMOWER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.probe_gatts.side_effect = BleakError

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_failed_is_connected(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, AUTOMOWER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.is_connected.side_effect = False
