"""Test the Mammotion Luba config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.web_exceptions import HTTPException
from bleak.backends.device import BLEDevice

from homeassistant import config_entries
from homeassistant.components.mammotion.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    CONF_BLE_DEVICES,
    CONF_DEVICE_NAME,
    CONF_STAY_CONNECTED_BLUETOOTH,
    CONF_USE_WIFI,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


# Helpers
def _get_mock_device(name="Luba-ABC123", address="aa:bb:cc:dd:ee:ff"):
    device = MagicMock(spec=BLEDevice)
    device.name = name
    device.address = address
    return device


def _get_discovery_info(name="Luba-ABC123", address="aa:bb:cc:dd:ee:ff"):
    discovery_info = MagicMock()
    discovery_info.name = name
    discovery_info.address = address.upper()
    return discovery_info


async def test_bluetooth_discovery_success(hass: HomeAssistant) -> None:
    """Test successful bluetooth discovery flow."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "Luba-ABC123"}

    # Confirm Bluetooth
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STAY_CONNECTED_BLUETOOTH: True},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"

    # Configure WiFi with credentials
    mock_http = MagicMock()
    mock_http.login_info.userInformation.userAccount = "user123"
    mock_http.login_v2 = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "password",
                CONF_USE_WIFI: True,
            },
        )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "user@example.com"
    assert result3["data"] == {
        CONF_ACCOUNTNAME: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_ACCOUNT_ID: "user123",
        CONF_DEVICE_NAME: "Luba-ABC123",
        CONF_USE_WIFI: True,
        CONF_BLE_DEVICES: {"Luba-ABC123": "aa:bb:cc:dd:ee:ff"},
    }
    assert result3["options"] == {CONF_STAY_CONNECTED_BLUETOOTH: True}


async def test_bluetooth_discovery_bluetooth_only(hass: HomeAssistant) -> None:
    """Test bluetooth discovery configuring usage without WiFi."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STAY_CONNECTED_BLUETOOTH: False},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"

    # Disable WiFi
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_USE_WIFI: False},
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Luba-ABC123"
    assert result3["data"] == {
        CONF_USE_WIFI: False,
        CONF_BLE_DEVICES: {"Luba-ABC123": "aa:bb:cc:dd:ee:ff"},
    }
    assert result3["options"] == {CONF_STAY_CONNECTED_BLUETOOTH: False}


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery aborts if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test discovery aborts if device name is not supported."""
    discovery_info = _get_discovery_info(name="Unknown-Device")
    device = _get_mock_device(name="Unknown-Device")

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery aborts if device is None (no longer present)."""
    discovery_info = _get_discovery_info()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_longer_present"


async def test_user_step_pick_discovery(hass: HomeAssistant) -> None:
    """Test user step picking a discovered device."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with (
        patch(
            "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
            return_value=[discovery_info],
        ),
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STAY_CONNECTED_BLUETOOTH: True},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"


async def test_user_step_no_discovery(hass: HomeAssistant) -> None:
    """Test user step with no discovered devices goes to wifi."""
    with patch(
        "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "wifi"


async def test_wifi_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test wifi step returns error on invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_http = MagicMock()
    mock_http.login_info = None
    mock_http.login_v2 = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "wrong",
                CONF_USE_WIFI: True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_wifi_step_connection_error(hass: HomeAssistant) -> None:
    """Test wifi step returns error on connection issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_http = MagicMock()
    mock_http.login_v2 = AsyncMock(side_effect=HTTPException(text="Conn Err"))

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "password",
                CONF_USE_WIFI: True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCOUNTNAME: "old@example.com",
            CONF_PASSWORD: "old_password",
            CONF_USE_WIFI: True,
        },
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCOUNTNAME: "new@example.com",
            CONF_PASSWORD: "new_password",
            CONF_USE_WIFI: False,
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.data[CONF_ACCOUNTNAME] == "new@example.com"
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_USE_WIFI] is False


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_STAY_CONNECTED_BLUETOOTH: False},
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_STAY_CONNECTED_BLUETOOTH: True}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_STAY_CONNECTED_BLUETOOTH] is True
