"""Contains unittests for config flow."""

from unittest.mock import patch

from aiopapouch.exceptions import (
    DeviceAuthError,
    DeviceConnectionError,
    DeviceParseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import data_entry_flow
from homeassistant.components.papouch.const import DOMAIN, WEB_MODE_INDEX
from homeassistant.core import HomeAssistant


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


@pytest.mark.parametrize(
    ("user_input_extra", "expected_password"),
    [
        ({"password": "admin", "port": 80}, "admin"),
        ({"port": 80}, None),
        ({"password": "", "port": 80}, ""),
    ],
)
async def test_user_success_variants(
    hass: HomeAssistant,
    mock_api_client,
    mock_setup_entry,
    user_input_extra,
    expected_password,
) -> None:
    """Test successful manual setup with different password configurations."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", **user_input_extra},
    )

    assert result2["result"].unique_id == "00:11:22:33:44:55"
    assert result2["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.50 - 00:11:22:33:44:55"
    assert result2["data"]["ip_address"] == "192.168.1.50"
    assert result2["data"]["password"] == expected_password
    assert result2["data"]["device_name"] == "Quido (Lab)"
    assert result2["data"]["port"] == 80
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_ip_format(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test handling of invalid IP address format during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "999.invalid.ip", "password": "supersecret"},
    )

    assert result2["type"] is data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"ip_address": "invalid_ip_format"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"ip_address": "192.168.1.50", "password": "supersecret"},
    )
    assert result3["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeviceConnectionError, {"base": "cannot_connect"}),
        (DeviceAuthError, {"base": "invalid_auth"}),
        (DeviceParseError, {"base": "parsing_error"}),
    ],
)
async def test_user_mode_errors(
    hass: HomeAssistant, mock_api_client, mock_setup_entry, side_effect, expected_error
) -> None:
    """Test handling of various errors during device mode check."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.side_effect = [side_effect, WEB_MODE_INDEX]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "wrong"},
    )

    assert result2["type"] is data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == expected_error
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"ip_address": "192.168.1.50", "password": "supersecret"},
    )
    assert result3["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("mode_value", "expected_reason"),
    [
        (-1, "mode_is_missing"),
        (1, "web_mode_required"),
    ],
)
async def test_user_mode_aborts(
    hass: HomeAssistant, mock_api_client, mode_value, expected_reason
) -> None:
    """Test config flow aborts for invalid device modes."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = mode_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50"},
    )

    assert result2["type"] is data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == expected_reason


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeviceAuthError, {"base": "invalid_auth"}),
        (DeviceConnectionError, {"base": "cannot_connect"}),
        (DeviceParseError, {"base": "parsing_error"}),
    ],
)
async def test_user_mac_errors(
    hass: HomeAssistant, mock_api_client, mock_setup_entry, side_effect, expected_error
) -> None:
    """Test manual flow aborts/errors if getting MAC address fails."""
    _, _, mock_mac, _ = mock_api_client
    mock_mac.side_effect = [side_effect, "00:11:22:33:44:55"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "password": "admin"},
    )

    assert result2["type"] is data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == expected_error
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"ip_address": "192.168.1.50", "password": "supersecret"},
    )
    assert result3["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY


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

    assert result2["type"] is data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
