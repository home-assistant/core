"""Test the ISEO Argo BLE config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.iseo_argo_ble.const import CONF_ADDRESS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_ADDRESS, MOCK_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def _patch_identity() -> None:
    """Patch identity generation to avoid real crypto in config flow tests."""
    mock_priv = MagicMock()
    mock_priv.private_numbers.return_value = MagicMock(private_value=12345678)
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.config_flow._generate_identity",
            return_value=mock_priv,
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        yield


async def test_bluetooth_discovery_abort_if_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery aborts for already-configured locks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(MOCK_ADDRESS),
        data={CONF_ADDRESS: MOCK_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_not_iseo(hass: HomeAssistant) -> None:
    """Test bluetooth discovery aborts for non-ISEO devices."""
    non_iseo_info = BluetoothServiceInfoBleak(
        name="SomeOtherDevice",
        address="11:22:33:44:55:66",
        rssi=-70,
        manufacturer_data={},
        service_data={},
        service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"],  # not ISEO
        source="local",
        device=MagicMock(),
        advertisement=MagicMock(),
        connectable=True,
        time=0,
        tx_power=None,
    )

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=non_iseo_info,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_iseo_device"


async def test_bluetooth_discovery_confirm_and_register(
    hass: HomeAssistant,
) -> None:
    """Test full bluetooth discovery → confirm → gw_register flow."""
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MOCK_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm the lock
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "gw_register"

    # Register gateway — mock the client
    mock_client = MagicMock()
    mock_client.setup_gateway = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.IseoClient",
        return_value=mock_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step aborts when no ISEO locks found nearby."""
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow._discover_locks",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_with_device(hass: HomeAssistant) -> None:
    """Test user step shows discovered devices and allows selection."""
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow._discover_locks",
        return_value=[MOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "errors" not in result or result["errors"] == {}

    # Select the device
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )
    # Should proceed to gw_register
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "gw_register"


async def test_gw_register_connection_error(hass: HomeAssistant) -> None:
    """Test gw_register handles connection error."""

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MOCK_SERVICE_INFO,
        )

    # Move to gw_register
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["step_id"] == "gw_register"

    mock_client = MagicMock()
    mock_client.setup_gateway = AsyncMock(side_effect=IseoConnectionError)

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.IseoClient",
        return_value=mock_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_gw_register_auth_error(hass: HomeAssistant) -> None:
    """Test gw_register handles auth error."""

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MOCK_SERVICE_INFO,
        )

    # Move to gw_register
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["step_id"] == "gw_register"

    mock_client = MagicMock()
    mock_client.setup_gateway = AsyncMock(side_effect=IseoAuthError)

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.IseoClient",
        return_value=mock_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "auth_failed"}


async def test_gw_register_no_ble_device(hass: HomeAssistant) -> None:
    """Test gw_register handles case where ble_device is None."""
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MOCK_SERVICE_INFO,
        )

    # Move to gw_register
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["step_id"] == "gw_register"

    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_gw_register_unknown_error(hass: HomeAssistant) -> None:
    """Test gw_register handles unknown error."""
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.is_iseo_advertisement",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MOCK_SERVICE_INFO,
        )

    # Move to gw_register
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["step_id"] == "gw_register"

    mock_client = MagicMock()
    mock_client.setup_gateway = AsyncMock(side_effect=Exception("BOOM"))
    with patch(
        "homeassistant.components.iseo_argo_ble.config_flow.IseoClient",
        return_value=mock_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input={}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}
