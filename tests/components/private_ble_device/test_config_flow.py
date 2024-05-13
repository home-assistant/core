"""Tests for private bluetooth device config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.private_ble_device import const
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.components.bluetooth import inject_bluetooth_service_info


def assert_form_error(result: FlowResult, key: str, value: str) -> None:
    """Assert that a flow returned a form error."""
    assert result["type"] == "form"
    assert result["errors"]
    assert result["errors"][key] == value


async def test_setup_user_no_bluetooth(
    hass: HomeAssistant, mock_bluetooth_adapters: None
) -> None:
    """Test setting up via user interaction when bluetooth is not enabled."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"


async def test_invalid_irk(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test invalid irk."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"irk": "irk:000000"}
    )
    assert_form_error(result, "irk", "irk_not_valid")


async def test_irk_not_found(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test irk not found."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"irk": "irk:00000000000000000000000000000000"},
    )
    assert_form_error(result, "irk", "irk_not_found")


async def test_flow_works(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test config flow works."""

    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name="Test Test Test",
            address="40:01:02:0a:c4:a6",
            rssi=-63,
            service_data={},
            manufacturer_data={},
            service_uuids=[],
            source="local",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    # Check you can finish the flow
    with patch(
        "homeassistant.components.private_ble_device.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"irk": "irk:00000000000000000000000000000000"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Test Test"
    assert result["data"] == {"irk": "00000000000000000000000000000000"}
    assert result["result"].unique_id == "00000000000000000000000000000000"


async def test_flow_works_by_base64(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test config flow works."""

    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name="Test Test Test",
            address="40:01:02:0a:c4:a6",
            rssi=-63,
            service_data={},
            manufacturer_data={},
            service_uuids=[],
            source="local",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    # Check you can finish the flow
    with patch(
        "homeassistant.components.private_ble_device.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"irk": "AAAAAAAAAAAAAAAAAAAAAA=="},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Test Test"
    assert result["data"] == {"irk": "00000000000000000000000000000000"}
    assert result["result"].unique_id == "00000000000000000000000000000000"
