"""Test the SystemNexa2 config flow."""

from ipaddress import ip_address
import socket
from unittest.mock import MagicMock, patch

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
async def test_full_flow(
    hass: HomeAssistant,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_NAME: "Test Device",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_device_id",
        data={
            CONF_HOST: "10.0.0.100",
            CONF_NAME: "Test Device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_MODEL: "Test Model",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_system_nexa_2_device_timeout")
async def test_connection_timeout(hass: HomeAssistant) -> None:
    """Test connection timeout handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_connection"
    assert result["description_placeholders"] == {"host": "10.0.0.131"}


@pytest.mark.usefixtures("mock_system_nexa_2_device_unknown_error")
async def test_connection_unknown_error(hass: HomeAssistant) -> None:
    """Test connection timeout handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_connection_error"
    assert result["description_placeholders"] == {"host": "10.0.0.131"}


async def test_empty_host(
    hass: HomeAssistant,
) -> None:
    """Test invalid hostname/IP address handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: ""},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_host"


async def test_invalid_hostname(
    hass: HomeAssistant,
) -> None:
    """Test invalid hostname/IP address handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test with hostname that cannot be resolved
    # Mock socket.gethostbyname to raise gaierror to cover the exception handling path
    with patch(
        "homeassistant.components.systemnexa2.config_flow.socket.gethostbyname",
        side_effect=socket.gaierror(-2, "Name or service not known"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "invalid-hostname.local"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_host"


@pytest.mark.usefixtures("mock_system_nexa_2_device")
@pytest.mark.usefixtures("mock_patch_get_host")
async def test_valid_hostname(
    hass: HomeAssistant,
) -> None:
    """Test invalid hostname/IP address handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test with hostname that cannot be resolved
    # Mock socket.gethostbyname to raise gaierror to cover the exception handling path
    # with patch(
    #     "homeassistant.components.systemnexa2.config_flow.socket.gethostbyname",
    # ):
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "valid-hostname.local"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert result["data"] == {
        CONF_HOST: "valid-hostname.local",
        CONF_NAME: "Test Device",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }


@pytest.mark.usefixtures("mock_system_nexa_2_device_unsupported")
async def test_unsupported_device(
    hass: HomeAssistant, mock_system_nexa_2_device_unsupported: MagicMock
) -> None:
    """Test unsupported device model handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
    assert result["description_placeholders"] == {
        "model": "Test Model",
        "sw_version": "Test Model Version",
    }


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test zeroconf discovery."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.0.131"),
        ip_addresses=[ip_address("10.0.0.131")],
        hostname="systemnexa2_test.local.",
        name="systemnexa2_test._systemnexa2._tcp.local.",
        port=80,
        type="_systemnexa2._tcp.local.",
        properties={
            "id": "test_device_id",
            "model": "Test Model",
            "version": "1.0.0",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "systemnexa2_test (Test Model)"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_NAME: "systemnexa2_test",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }


async def test_device_with_none_values(
    hass: HomeAssistant,
    mock_system_nexa_2_device: MagicMock,
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
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_zeroconf_discovery_none_values(
    hass: HomeAssistant,
) -> None:
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
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
