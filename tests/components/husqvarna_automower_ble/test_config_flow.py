"""Test the Husqvarna Bluetooth config flow."""

from unittest.mock import Mock, patch

from automower_ble.protocol import ResponseResult
from bleak import BleakError
import pytest

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    AUTOMOWER_MISSING_MANUFACTURER_DATA_SERVICE_INFO,
    AUTOMOWER_SERVICE_INFO_MOWER,
    AUTOMOWER_SERVICE_INFO_SERIAL,
    AUTOMOWER_UNNAMED_SERVICE_INFO,
    MISSING_SERVICE_SERVICE_INFO,
    WATER_TIMER_SERVICE_INFO,
)

from tests.common import MockConfigEntry
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

    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # mock connection error
    with patch(
        "homeassistant.components.husqvarna_automower_ble.config_flow.HusqvarnaAutomowerBleConfigFlow.probe_mower",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
                CONF_PIN: "1234",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "1234",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000001"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
        CONF_CLIENT_ID: 1197489078,
        CONF_PIN: "1234",
    }


async def test_user_selection_incorrect_pin(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Try non numeric pin
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "ABCD",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_pin"}

    # Try wrong PIN
    mock_automower_client.connect.return_value = ResponseResult.INVALID_PIN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_automower_client.connect.return_value = ResponseResult.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
        CONF_CLIENT_ID: 1197489078,
        CONF_PIN: "1234",
    }


@pytest.mark.parametrize(
    "service_info",
    [AUTOMOWER_SERVICE_INFO_MOWER, AUTOMOWER_SERVICE_INFO_SERIAL],
)
async def test_bluetooth(
    hass: HomeAssistant, service_info: BluetoothServiceInfo
) -> None:
    """Test bluetooth device discovery."""

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000003"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
        CONF_CLIENT_ID: 1197489078,
        CONF_PIN: "1234",
    }


async def test_bluetooth_incorrect_pin(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=AUTOMOWER_SERVICE_INFO_SERIAL,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Try non numeric pin
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "ABCD",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "invalid_pin"}

    # Try wrong PIN
    mock_automower_client.connect.return_value = ResponseResult.INVALID_PIN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_automower_client.connect.return_value = ResponseResult.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000003"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
        CONF_CLIENT_ID: 1197489078,
        CONF_PIN: "1234",
    }


async def test_bluetooth_unknown_error(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=AUTOMOWER_SERVICE_INFO_SERIAL,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    mock_automower_client.connect.return_value = ResponseResult.UNKNOWN_ERROR

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


async def test_bluetooth_not_paired(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=AUTOMOWER_SERVICE_INFO_SERIAL,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    mock_automower_client.connect.return_value = ResponseResult.NOT_ALLOWED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    mock_automower_client.connect.return_value = ResponseResult.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Husqvarna Automower"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000003"

    assert result["data"] == {
        CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
        CONF_CLIENT_ID: 1197489078,
        CONF_PIN: "1234",
    }


@pytest.mark.parametrize(
    "service_info",
    [
        AUTOMOWER_MISSING_MANUFACTURER_DATA_SERVICE_INFO,
        MISSING_SERVICE_SERVICE_INFO,
        WATER_TIMER_SERVICE_INFO,
    ],
)
async def test_bluetooth_invalid(
    hass: HomeAssistant, service_info: BluetoothServiceInfo
) -> None:
    """Test bluetooth device discovery with invalid data."""

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_successful_reauth(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can select a device."""

    mock_config_entry.add_to_hass(hass)

    await hass.async_block_till_done(wait_background_tasks=True)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Try non numeric pin
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "ABCD",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_pin"}

    # Try connection error
    mock_automower_client.connect.return_value = ResponseResult.UNKNOWN_ERROR
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "5678",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # Try wrong PIN
    mock_automower_client.connect.return_value = ResponseResult.INVALID_PIN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "5678",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_automower_client.connect.return_value = ResponseResult.OK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "1234",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries("husqvarna_automower_ble")) == 1

    assert (
        mock_config_entry.data[CONF_ADDRESS] == "00000000-0000-0000-0000-000000000003"
    )
    assert mock_config_entry.data[CONF_CLIENT_ID] == 1197489078
    assert mock_config_entry.data[CONF_PIN] == "1234"


async def test_user_unable_to_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.connect.side_effect = BleakError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "1234",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_failed_reauth(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can select a device."""

    mock_config_entry.add_to_hass(hass)

    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.connect.side_effect = BleakError

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: "5678",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can select a device."""

    mock_config_entry.add_to_hass(hass)

    await hass.async_block_till_done(wait_background_tasks=True)

    # Test we should not discover the already configured device
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
            CONF_PIN: "1234",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_exception_probe(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, AUTOMOWER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.probe_gatts.side_effect = BleakError

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_exception_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can select a device."""

    mock_config_entry.add_to_hass(hass)

    await hass.async_block_till_done(wait_background_tasks=True)

    mock_automower_client.connect.side_effect = BleakError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000001",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.ABORT
