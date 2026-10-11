"""Contains unittests for config flow."""

from unittest.mock import patch

from aiopapouch.exceptions import (
    DeviceAuthError,
    DeviceConnectionError,
    DeviceLogicError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.papouch.const import DOMAIN, WEB_MODE_INDEX
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Fixture to mock the integration entry setup."""
    with patch(
        "homeassistant.components.papouch.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_api_client():
    """Fixture to mock API client fetch info, device mode and MAC methods."""
    with (
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.fetch_info"
        ) as mock_fetch,
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.get_device_mode",
            return_value=WEB_MODE_INDEX,
        ) as mock_mode,
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.get_device_mac",
            return_value="00:11:22:33:44:55",
        ) as mock_mac,
        patch(
            "homeassistant.components.papouch.utils.PapouchHTTPClient.get_device_info",
            return_value=("Quido", "Lab"),
        ) as mock_info,
    ):
        yield mock_fetch, mock_mode, mock_mac, mock_info


async def test_user_success(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test successful manual setup of the integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ip_address": "192.168.1.50",
            "password": "admin",
            "port": 80,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.50"
    assert result2["data"]["ip_address"] == "192.168.1.50"
    assert result2["data"]["password"] == "admin"
    assert result2["data"]["device_name"] == "Quido (Lab)"
    assert result2["data"]["port"] == 80
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_ip_format(hass: HomeAssistant) -> None:
    """Test handling of invalid IP address format during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "999.invalid.ip", "password": "supersecret"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"]["ip_address"] == "invalid_ip_format"


async def test_user_connection_error(hass: HomeAssistant, mock_api_client) -> None:
    """Test handling of connection errors during first step."""
    mock_fetch, _, _, _ = mock_api_client
    mock_fetch.side_effect = DeviceConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "supersecret"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_auth_error(hass: HomeAssistant, mock_api_client) -> None:
    """Test handling of authentication errors during first step."""
    mock_fetch, _, _, _ = mock_api_client
    mock_fetch.side_effect = DeviceAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "wrong"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_mode_missing(hass: HomeAssistant, mock_api_client) -> None:
    """Test config flow aborts when the device mode is missing."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = -1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "mode_is_missing"


async def test_user_web_mode_required(hass: HomeAssistant, mock_api_client) -> None:
    """Test config flow aborts when the device is not in web mode."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 1  # Using a mode other than WEB_MODE_INDEX

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "web_mode_required"


async def test_user_mac_auth_error(
    hass: HomeAssistant,
    mock_api_client,
) -> None:
    """Test auth error gracefully failing when retrieving MAC address."""
    _, _, mock_mac, _ = mock_api_client
    mock_mac.side_effect = DeviceAuthError("Bad password")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "ip_address": "192.168.1.50",
            "password": "wrong_password",
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_mac_connection_error(
    hass: HomeAssistant,
    mock_api_client,
) -> None:
    """Test manual flow aborts if getting MAC address fails due to logic/connection error."""
    _, _, mock_mac, _ = mock_api_client
    mock_mac.side_effect = DeviceLogicError("No MAC found")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "admin"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_already_configured(hass: HomeAssistant, mock_api_client) -> None:
    """Test that manual IP entry aborts if the IP is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={"ip_address": "192.168.1.50"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_user_success_no_password(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test successful manual setup when no password is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ip_address": "192.168.1.50",
            "port": 80,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.50"
    assert result2["data"]["ip_address"] == "192.168.1.50"
    assert result2["data"]["password"] is None
    assert result2["data"]["device_name"] == "Quido (Lab)"
    assert result2["data"]["port"] == 80
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_success_empty_string_password(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test successful manual setup when password is an empty string."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ip_address": "192.168.1.50",
            "password": "",
            "port": 80,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"]["password"] is None
