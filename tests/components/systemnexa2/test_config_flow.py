"""Test the SystemNexa2 config flow."""

from ipaddress import ip_address
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sn2 import InformationData, InformationUpdate

from homeassistant.components.systemnexa2 import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_NAME: "Test Device",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }
    assert result["result"].unique_id == "test_device_id"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (TimeoutError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_connection_error_and_recovery(
    hass: HomeAssistant,
    mock_system_nexa_2_device: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error_key: str,
) -> None:
    """Test connection error handling and recovery."""
    mock_system_nexa_2_device.return_value.get_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # Remove the side effect and retry - should succeed now
    device = mock_system_nexa_2_device.return_value
    device.get_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_empty_host(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test invalid hostname/IP address handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_invalid_host(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test invalid hostname/IP address handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.systemnexa2.config_flow.socket.gethostbyname",
        side_effect=socket.gaierror(-2, "Name or service not known"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "invalid-hostname.local"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_system_nexa_2_device")
@pytest.mark.usefixtures("mock_patch_get_host")
async def test_valid_hostname(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test valid hostname handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "valid-hostname.local"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert result["data"] == {
        CONF_HOST: "valid-hostname.local",
        CONF_NAME: "Test Device",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_unsupported_device(
    hass: HomeAssistant, mock_system_nexa_2_device: MagicMock
) -> None:
    """Test unsupported device model handling."""
    mock_system_nexa_2_device.is_device_supported.return_value = (False, "Err")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
    assert result["description_placeholders"] == {
        "model": "Test Model",
        "sw_version": "Test Model Version",
    }


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=mock_zeroconf_discovery_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "systemnexa2_test (Test Model)"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_NAME: "systemnexa2_test",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test we abort zeroconf discovery if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=mock_zeroconf_discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_device_with_none_values(
    hass: HomeAssistant, mock_system_nexa_2_device: MagicMock
) -> None:
    """Test device with None values in info is rejected."""

    device = mock_system_nexa_2_device.return_value
    # Create new InformationData with None unique_id
    device.info_data = InformationData(
        name="Test Device",
        model="Test Model",
        unique_id=None,
        sw_version="Test Model Version",
        hw_version="Test HW Version",
        wifi_dbm=-50,
        wifi_ssid="Test WiFi SSID",
        dimmable=False,
    )
    device.get_info.return_value = InformationUpdate(information=device.info_data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_zeroconf_discovery_none_values(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with None property values is rejected."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.0.131"),
        ip_addresses=[ip_address("10.0.0.131")],
        hostname="systemnexa2_test.local.",
        name="systemnexa2_test._systemnexa2._tcp.local.",
        port=80,
        type="_systemnexa2._tcp.local.",
        properties={
            "id": None,
            "model": "Test Model",
            "version": "1.0.0",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
