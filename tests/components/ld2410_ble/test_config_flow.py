"""Test the LD2410 BLE Bluetooth config flow."""
from unittest.mock import patch

from bleak import BleakError

from homeassistant import config_entries
from homeassistant.components.ld2410_ble.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import LD2410_BLE_DISCOVERY_INFO, NOT_LD2410_BLE_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.ld2410_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_LD2410_BLE_DISCOVERY_INFO, LD2410_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
    ), patch(
        "homeassistant.components.ld2410_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == LD2410_BLE_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == LD2410_BLE_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.ld2410_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_LD2410_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_no_new_devices_found(hass: HomeAssistant) -> None:
    """Test user step with only existing devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
        },
        unique_id=LD2410_BLE_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ld2410_ble.config_flow.async_discovered_service_info",
        return_value=[LD2410_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step and we cannot connect."""
    with patch(
        "homeassistant.components.ld2410_ble.config_flow.async_discovered_service_info",
        return_value=[LD2410_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
        side_effect=BleakError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
    ), patch(
        "homeassistant.components.ld2410_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == LD2410_BLE_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
    }
    assert result3["result"].unique_id == LD2410_BLE_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_unknown_exception(hass: HomeAssistant) -> None:
    """Test user step with an unknown exception."""
    with patch(
        "homeassistant.components.ld2410_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_LD2410_BLE_DISCOVERY_INFO, LD2410_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
    ), patch(
        "homeassistant.components.ld2410_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == LD2410_BLE_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
    }
    assert result3["result"].unique_id == LD2410_BLE_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LD2410_BLE_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ld2410_ble.config_flow.LD2410BLE.initialise",
    ), patch(
        "homeassistant.components.ld2410_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == LD2410_BLE_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == LD2410_BLE_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1
