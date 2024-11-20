"""Test the Motionblinds Bluetooth config flow."""

from unittest.mock import AsyncMock, Mock, patch

from motionblindsble.const import MotionBlindType
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.motionblinds_ble import const
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("motionblinds_ble_connect")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_manual_success(
    hass: HomeAssistant,
    blind_type: MotionBlindType,
    mac_code: str,
    address: str,
    local_name: str,
    display_name: str,
) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: mac_code},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: blind_type.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == display_name
    assert result["data"] == {
        CONF_ADDRESS: address,
        const.CONF_LOCAL_NAME: local_name,
        const.CONF_MAC_CODE: mac_code,
        const.CONF_BLIND_TYPE: blind_type.name.lower(),
    }
    assert result["options"] == {}


@pytest.mark.usefixtures("motionblinds_ble_connect")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_manual_error_invalid_mac(
    hass: HomeAssistant,
    mac_code: str,
    address: str,
    local_name: str,
    display_name: str,
    blind_type: MotionBlindType,
) -> None:
    """Invalid MAC code error flow manually initialized by the user."""

    # Initialize
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Try invalid MAC code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: "AABBCC"},  # A MAC code should be 4 characters
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_INVALID_MAC_CODE}

    # Recover
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: mac_code},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Finish flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: blind_type.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == display_name
    assert result["data"] == {
        CONF_ADDRESS: address,
        const.CONF_LOCAL_NAME: local_name,
        const.CONF_MAC_CODE: mac_code,
        const.CONF_BLIND_TYPE: blind_type.name.lower(),
    }
    assert result["options"] == {}


@pytest.mark.usefixtures("motionblinds_ble_connect")
async def test_config_flow_manual_error_no_bluetooth_adapter(
    hass: HomeAssistant,
    mac_code: str,
) -> None:
    """No Bluetooth adapter error flow manually initialized by the user."""

    # Try step_user with zero Bluetooth adapters
    with patch(
        "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
        return_value=0,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == const.ERROR_NO_BLUETOOTH_ADAPTER

    # Try discovery with zero Bluetooth adapters
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
        return_value=0,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_MAC_CODE: mac_code},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == const.ERROR_NO_BLUETOOTH_ADAPTER


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_manual_error_could_not_find_motor(
    hass: HomeAssistant,
    motionblinds_ble_connect: tuple[AsyncMock, Mock],
    mac_code: str,
    local_name: str,
    display_name: str,
    address: str,
    blind_type: MotionBlindType,
) -> None:
    """Could not find motor error flow manually initialized by the user."""

    # Initialize
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Try with MAC code that cannot be found
    motionblinds_ble_connect[1].name = "WRONG_NAME"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: mac_code},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_COULD_NOT_FIND_MOTOR}

    # Recover
    motionblinds_ble_connect[1].name = local_name
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: mac_code},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Finish flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: blind_type.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == display_name
    assert result["data"] == {
        CONF_ADDRESS: address,
        const.CONF_LOCAL_NAME: local_name,
        const.CONF_MAC_CODE: mac_code,
        const.CONF_BLIND_TYPE: blind_type.name.lower(),
    }
    assert result["options"] == {}


async def test_config_flow_manual_error_no_devices_found(
    hass: HomeAssistant,
    motionblinds_ble_connect: tuple[AsyncMock, Mock],
    mac_code: str,
) -> None:
    """No devices found error flow manually initialized by the user."""

    # Initialize
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Try with zero found bluetooth devices
    motionblinds_ble_connect[0].discover.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: mac_code},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == const.ERROR_NO_DEVICES_FOUND


@pytest.mark.usefixtures("motionblinds_ble_connect")
async def test_config_flow_bluetooth_success(
    hass: HomeAssistant,
    mac_code: str,
    service_info: BluetoothServiceInfoBleak,
    address: str,
    local_name: str,
    display_name: str,
    blind_type: MotionBlindType,
) -> None:
    """Successful bluetooth discovery flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: blind_type.name.lower()},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == display_name
    assert result["data"] == {
        CONF_ADDRESS: address,
        const.CONF_LOCAL_NAME: local_name,
        const.CONF_MAC_CODE: mac_code,
        const.CONF_BLIND_TYPE: blind_type.name.lower(),
    }
    assert result["options"] == {}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.OPTION_PERMANENT_CONNECTION: True,
            const.OPTION_DISCONNECT_TIME: 10,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
