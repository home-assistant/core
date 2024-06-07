"""Test the Motionblinds Bluetooth config flow."""

from unittest.mock import patch

from motionblindsble.const import MotionBlindType

from homeassistant import config_entries
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.motionblinds_ble import const
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_ADDRESS, TEST_MAC, TEST_NAME

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

TEST_BLIND_TYPE = MotionBlindType.ROLLER.name.lower()

BLIND_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=TEST_NAME,
    address=TEST_ADDRESS,
    device=generate_ble_device(
        address="cc:cc:cc:cc:cc:cc",
        name=TEST_NAME,
    ),
    rssi=-61,
    manufacturer_data={000: b"test"},
    service_data={
        "test": bytearray(b"0000"),
    },
    service_uuids=[
        "test",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={000: b"test"},
        service_uuids=["test"],
    ),
    connectable=True,
    time=0,
    tx_power=-127,
)


async def test_config_flow_manual_success(
    hass: HomeAssistant, motionblinds_ble_connect
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
        {const.CONF_MAC_CODE: TEST_MAC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: MotionBlindType.ROLLER.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Motionblind {TEST_MAC.upper()}"
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}


async def test_config_flow_manual_error_invalid_mac(
    hass: HomeAssistant, motionblinds_ble_connect
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
        {const.CONF_MAC_CODE: TEST_MAC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Finish flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: MotionBlindType.ROLLER.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Motionblind {TEST_MAC.upper()}"
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}


async def test_config_flow_manual_error_no_bluetooth_adapter(
    hass: HomeAssistant, motionblinds_ble_connect
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
            {const.CONF_MAC_CODE: TEST_MAC},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == const.ERROR_NO_BLUETOOTH_ADAPTER


async def test_config_flow_manual_error_could_not_find_motor(
    hass: HomeAssistant, motionblinds_ble_connect
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
        {const.CONF_MAC_CODE: TEST_MAC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_COULD_NOT_FIND_MOTOR}

    # Recover
    motionblinds_ble_connect[1].name = TEST_NAME
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: TEST_MAC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Finish flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: MotionBlindType.ROLLER.name.lower()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Motionblind {TEST_MAC.upper()}"
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}


async def test_config_flow_manual_error_no_devices_found(
    hass: HomeAssistant, motionblinds_ble_connect
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
        {const.CONF_MAC_CODE: TEST_MAC},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == const.ERROR_NO_DEVICES_FOUND


async def test_config_flow_bluetooth_success(
    hass: HomeAssistant, motionblinds_ble_connect
) -> None:
    """Successful bluetooth discovery flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLIND_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: MotionBlindType.ROLLER.name.lower()},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Motionblind {TEST_MAC.upper()}"
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}
