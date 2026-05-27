"""Tests for the energieleser config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from energieleser import (
    EnergieleserConnectionError,
    EnergieleserUnknownDeviceError,
    GasleserDevice,
)
import pytest

from homeassistant.components.energieleser.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import GASLESER_DEVICE_ID, STROMLESER_DEVICE_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_user_flow_stromleser(hass: HomeAssistant) -> None:
    """Test a successful manual user flow for a stromleser device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "stromleser.one"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"]["device_id"] == STROMLESER_DEVICE_ID
    assert result["result"].unique_id == STROMLESER_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_gasleser(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_device: GasleserDevice,
) -> None:
    """Test a successful manual user flow for a gasleser device."""
    mock_energieleser_client.get_device.return_value = mock_gasleser_device

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.101"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device_id"] == GASLESER_DEVICE_ID
    assert result["result"].unique_id == GASLESER_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            EnergieleserConnectionError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EnergieleserUnknownDeviceError("FOO_0000000001"),
            "unknown_device_type",
            id="unknown_device_type",
        ),
    ],
)
async def test_user_flow_client_errors(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test client errors during the user flow."""
    mock_energieleser_client.get_device.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.99"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate device is aborted."""
    mock_stromleser_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="stromleser-one.local.",
            name="stromleser-one",
            port=80,
            properties={},
            type="_stromleser._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["device_type"] == "stromleser.one"
    assert result["description_placeholders"]["device_id"] == STROMLESER_DEVICE_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "stromleser.one"
    assert result["data"]["device_id"] == STROMLESER_DEVICE_ID


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(
            EnergieleserConnectionError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EnergieleserUnknownDeviceError("FOO_0000000001"),
            "unknown_device_type",
            id="unknown_device_type",
        ),
    ],
)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Test that a zeroconf flow aborts on client errors."""
    mock_energieleser_client.get_device.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="stromleser-one.local.",
            name="stromleser-one",
            port=80,
            properties={},
            type="_stromleser._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
