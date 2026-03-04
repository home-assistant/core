"""Test the Flic Button config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError

from homeassistant.components.flic_button.config_flow import FlicButtonConfigFlow
from homeassistant.components.flic_button.const import (
    CONF_BUTTON_UUID,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
    PushTwistMode,
)
from homeassistant.components.flic_button.flic_client import (
    FlicAuthenticationError,
    FlicPairingError,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DUO_SERIAL,
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_BUTTON_UUID,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_flic2_service_info,
    create_twist_service_info,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_user_flow_shows_discovery_progress(hass: HomeAssistant) -> None:
    """Test user-initiated flow starts discovery progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "wait_for_discovery"

    # Abort the flow to cancel the background discovery task
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_bluetooth_discovery_flic2(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery flow for Flic 2 shows confirmation."""
    service_info = create_flic2_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )

    # Bluetooth discovery shows confirmation form before pairing
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


async def test_bluetooth_discovery_twist(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery flow for Flic Twist shows confirmation."""
    service_info = create_twist_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )

    # Bluetooth discovery shows confirmation form before pairing
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery when device is already configured."""
    service_info = create_flic2_service_info()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FLIC2_ADDRESS,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_pairing_success_flic2(hass: HomeAssistant) -> None:
    """Test successful pairing flow for Flic 2."""
    service_info = create_flic2_service_info()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        return_value=(
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            FLIC2_SERIAL,
            TEST_BATTERY_LEVEL,
            TEST_SIG_BITS,
            None,
            10,
        )
    )

    with (
        patch(
            "homeassistant.components.flic_button.config_flow.FlicClient",
            return_value=mock_client,
        ),
        patch_async_setup_entry(),
    ):
        # Bluetooth discovery shows confirmation first
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        # Confirm → pair form
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"

        # Submit pair form → performs pairing
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    # No button UUID → direct entry creation (no firmware check)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Flic 2 ({FLIC2_SERIAL})"
    assert result["data"] == {
        CONF_ADDRESS: FLIC2_ADDRESS,
        CONF_PAIRING_ID: TEST_PAIRING_ID,
        CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
        CONF_SERIAL_NUMBER: FLIC2_SERIAL,
        "battery_level": TEST_BATTERY_LEVEL,
        CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
        CONF_SIG_BITS: TEST_SIG_BITS,
    }


async def test_pairing_success_duo(hass: HomeAssistant) -> None:
    """Test successful pairing flow for Flic Duo (detected from serial prefix)."""
    service_info = create_flic2_service_info()  # Duo uses same service UUID as Flic 2

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    # Duo is detected by serial number prefix "D"
    mock_client.full_verify_pairing = AsyncMock(
        return_value=(
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            DUO_SERIAL,  # "D" prefix indicates Duo
            TEST_BATTERY_LEVEL,
            TEST_SIG_BITS,
            None,
            10,
        )
    )

    with (
        patch(
            "homeassistant.components.flic_button.config_flow.FlicClient",
            return_value=mock_client,
        ),
        patch_async_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )
        assert result["step_id"] == "bluetooth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["step_id"] == "pair"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Flic Duo ({DUO_SERIAL})"
    assert result["data"][CONF_DEVICE_TYPE] == DeviceType.DUO.value


async def test_pairing_success_twist(hass: HomeAssistant) -> None:
    """Test successful pairing flow for Flic Twist."""
    service_info = create_twist_service_info()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        return_value=(
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            TWIST_SERIAL,
            TEST_BATTERY_LEVEL,
            TEST_SIG_BITS,
            TEST_BUTTON_UUID,
            10,
        )
    )

    with (
        patch(
            "homeassistant.components.flic_button.config_flow.FlicClient",
            return_value=mock_client,
        ),
        patch_async_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )
        assert result["step_id"] == "bluetooth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["step_id"] == "pair"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Flic Twist ({TWIST_SERIAL})"
    assert result["data"][CONF_DEVICE_TYPE] == DeviceType.TWIST.value
    assert result["data"][CONF_BUTTON_UUID] == TEST_BUTTON_UUID.hex()


async def _init_bt_and_confirm(hass: HomeAssistant, service_info):
    """Start bluetooth flow and confirm, returning pair form result and flow_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "pair"
    return result


async def test_pairing_error_cannot_connect_bleak(hass: HomeAssistant) -> None:
    """Test pairing error when BleakError occurs during connection."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock(side_effect=BleakError("Connection failed"))
    mock_client.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_pairing_error_cannot_connect_timeout(hass: HomeAssistant) -> None:
    """Test pairing error when timeout occurs during connection."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock(side_effect=TimeoutError())
    mock_client.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_pairing_error_pairing_failed(hass: HomeAssistant) -> None:
    """Test pairing error when FlicPairingError occurs."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        side_effect=FlicPairingError("Pairing failed")
    )

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "pairing_failed"}


async def test_pairing_error_invalid_signature(hass: HomeAssistant) -> None:
    """Test pairing error when FlicAuthenticationError occurs."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        side_effect=FlicAuthenticationError("Invalid signature")
    )

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "invalid_signature"}


async def test_pairing_error_unknown(hass: HomeAssistant) -> None:
    """Test pairing error when unexpected exception occurs."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        side_effect=RuntimeError("Unexpected error")
    )

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "unknown"}


async def test_pairing_retry_after_error(hass: HomeAssistant) -> None:
    """Test pairing can be retried after an error."""
    service_info = create_flic2_service_info()

    result = await _init_bt_and_confirm(hass, service_info)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock(side_effect=BleakError("Connection failed"))
    mock_client.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.flic_button.config_flow.FlicClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt succeeds
    mock_client.connect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        return_value=(
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            FLIC2_SERIAL,
            TEST_BATTERY_LEVEL,
            TEST_SIG_BITS,
            None,
            10,
        )
    )

    with (
        patch(
            "homeassistant.components.flic_button.config_flow.FlicClient",
            return_value=mock_client,
        ),
        patch_async_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_twist_device(hass: HomeAssistant) -> None:
    """Test options flow for Flic Twist device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            "battery_level": TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR}


async def test_options_flow_non_twist_device_aborts(hass: HomeAssistant) -> None:
    """Test options flow aborts for non-Twist devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            "battery_level": TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_twist_device"


async def test_config_flow_version() -> None:
    """Test config flow version is set correctly."""
    flow = FlicButtonConfigFlow()
    assert flow.VERSION == 1
    assert flow.MINOR_VERSION == 1


async def test_bluetooth_confirm_step(hass: HomeAssistant) -> None:
    """Test bluetooth_confirm step shows form and proceeds to pair."""
    service_info = create_flic2_service_info()

    # Start the flow - shows bluetooth confirmation form
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm → proceeds to pair form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
