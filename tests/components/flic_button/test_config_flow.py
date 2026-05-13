"""Test the Flic Button config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
from pyflic_ble import (
    DeviceType,
    FlicAuthenticationError,
    FlicPairingError,
    PushTwistMode,
)
import pytest

from homeassistant.components.flic_button.config_flow import FlicButtonConfigFlow
from homeassistant.components.flic_button.const import (
    CONF_DEVICE_TYPE,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ADDRESS_FOR_DEVICE_TYPE,
    DUO_SERIAL,
    FLIC2_SERIAL,
    MODEL_NAME_FOR_DEVICE_TYPE,
    TEST_BATTERY_LEVEL,
    TEST_BUTTON_UUID,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    create_flic2_service_info,
    service_info_for_device_type,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_discovered_service_info(
    device_type: DeviceType,
) -> Generator[MagicMock]:
    """Patch async_discovered_service_info to return the matching device."""
    service_info = service_info_for_device_type(device_type)
    with patch(
        "homeassistant.components.flic_button.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ) as mock:
        yield mock


async def _init_bt_flow(hass: HomeAssistant, device_type: DeviceType) -> dict:
    """Start a bluetooth flow with the device present in HA's discovered cache."""
    service_info = service_info_for_device_type(device_type)
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )


async def test_user_flow_shows_discovery_progress(hass: HomeAssistant) -> None:
    """Test user-initiated flow starts discovery progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "wait_for_discovery"

    # Cancel the background discovery task so it does not run after the test
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()

    # Subsequent inspection should show no remaining flows in progress
    assert not hass.config_entries.flow.async_progress(include_uninitialized=True)


@pytest.mark.usefixtures("mock_discovered_service_info")
@pytest.mark.parametrize(
    ("device_type", "serial"),
    [
        (DeviceType.FLIC2, FLIC2_SERIAL),
        (DeviceType.DUO, DUO_SERIAL),
        (DeviceType.TWIST, "T12345"),
    ],
)
async def test_pairing_success(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_setup_entry: AsyncMock,
    device_type: DeviceType,
    serial: str,
) -> None:
    """Test successful pairing flow for each supported device type."""
    address = ADDRESS_FOR_DEVICE_TYPE[device_type]
    model = MODEL_NAME_FOR_DEVICE_TYPE[device_type]
    # Override default fixture serial for the chosen device
    mock_flic_client.full_verify_pairing.return_value = (
        TEST_PAIRING_ID,
        TEST_PAIRING_KEY,
        serial,
        TEST_BATTERY_LEVEL,
        TEST_SIG_BITS,
        TEST_BUTTON_UUID if device_type is DeviceType.TWIST else None,
        10,
    )

    result = await _init_bt_flow(hass, device_type)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{model} ({serial})"
    assert result["result"].unique_id == address
    assert result["data"][CONF_ADDRESS] == address
    assert result["data"][CONF_DEVICE_TYPE] == device_type.value
    assert result["data"][CONF_SERIAL_NUMBER] == serial


@pytest.mark.usefixtures("mock_discovered_service_info")
async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Bluetooth discovery when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _init_bt_flow(hass, DeviceType.FLIC2)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_discovered_service_info")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BleakError("Connection failed"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (FlicPairingError("Pairing failed"), "pairing_failed"),
        (FlicAuthenticationError("Invalid signature"), "invalid_signature"),
        (RuntimeError("Unexpected error"), "unknown"),
    ],
)
async def test_pairing_errors_recover(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Each pairing error path falls back to the form and recovers to CREATE_ENTRY."""
    # Route the failure through whichever client method is invoked first
    if isinstance(side_effect, (BleakError, TimeoutError)):
        mock_flic_client.connect.side_effect = side_effect
    else:
        mock_flic_client.full_verify_pairing.side_effect = side_effect

    result = await _init_bt_flow(hass, DeviceType.FLIC2)
    assert result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": error}

    # Recover and complete the flow
    mock_flic_client.connect.side_effect = None
    mock_flic_client.full_verify_pairing.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_options_flow_twist_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow for Flic Twist device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR}


async def test_options_flow_not_supported_for_non_twist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow is not supported for non-Twist devices."""
    mock_config_entry.add_to_hass(hass)
    assert not FlicButtonConfigFlow.async_supports_options_flow(mock_config_entry)


async def test_bluetooth_confirm_device_no_longer_advertising(
    hass: HomeAssistant,
) -> None:
    """Test Bluetooth discovery falls back to scanner when the device disappears."""
    service_info = create_flic2_service_info()

    with patch(
        "homeassistant.components.flic_button.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "wait_for_discovery"

    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
