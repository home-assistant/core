"""Test the MotionBlinds BLE config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.motionblinds_ble import const
from homeassistant.core import HomeAssistant

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device
from tests.components.motionblinds_ble.conftest import TEST_ADDRESS, TEST_MAC, TEST_NAME

TEST_BLIND_TYPE = const.MotionBlindType.ROLLER

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
)


async def test_config_flow_manual_success(
    hass: HomeAssistant, motionblinds_ble_connect
) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: TEST_MAC},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: const.MotionBlindType.ROLLER},
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MotionBlind {TEST_MAC.upper()}"
    assert result["data"] == {
        const.CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}

    # Second setup to test already configured error
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_config_flow_manual_errors(
    hass: HomeAssistant, motionblinds_ble_connect
) -> None:
    """Errors during flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: "ab:cd:ef:gh"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_INVALID_MAC_CODE}

    with patch(
        "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
        return_value=0,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_MAC_CODE: TEST_MAC},
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_NO_BLUETOOTH_ADAPTER}

    motionblinds_ble_connect[1].name = "WRONG_NAME"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: TEST_MAC},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_COULD_NOT_FIND_MOTOR}

    motionblinds_ble_connect[0].discover.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: TEST_MAC},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": const.ERROR_NO_DEVICES_FOUND}


async def test_config_flow_bluetooth_success(
    hass: HomeAssistant, motionblinds_ble_connect
) -> None:
    """Successful bluetooth discovery flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLIND_SERVICE_INFO,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: const.MotionBlindType.ROLLER},
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MotionBlind {TEST_MAC.upper()}"
    assert result["data"] == {
        const.CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}
