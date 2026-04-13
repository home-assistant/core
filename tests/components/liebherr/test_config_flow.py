"""Test the liebherr config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MOCK_API_KEY = "test-api-key"
MOCK_USER_INPUT = {CONF_API_KEY: MOCK_API_KEY}

MOCK_ZEROCONF_SERVICE_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.100"),
    ip_addresses=[ip_address("192.168.1.100")],
    port=80,
    hostname="liebherr-device.local.",
    type="_http._tcp.local.",
    name="liebherr-fridge._http._tcp.local.",
    properties={},
)


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Liebherr"
    assert result.get("data") == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (LiebherrAuthenticationError("Invalid"), "invalid_auth"),
        (LiebherrConnectionError("Failed"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_form_errors_with_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test error handling with successful recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    # Trigger error
    mock_liebherr_client.get_devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": expected_error}

    # Recover and complete successfully
    mock_liebherr_client.get_devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Liebherr"
    assert result.get("data") == MOCK_USER_INPUT


async def test_form_no_devices(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test we handle no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    mock_liebherr_client.get_devices.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "no_devices"


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test zeroconf discovery triggers the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Liebherr"
    assert result.get("data") == MOCK_USER_INPUT


async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf discovery aborts if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_SERVICE_INFO,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    new_api_key = "new-api-key"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: new_api_key}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == new_api_key


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (LiebherrAuthenticationError("Invalid"), "invalid_auth"),
        (LiebherrConnectionError("Failed"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_reauth_flow_errors_with_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth flow error handling with successful recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    # Trigger error
    mock_liebherr_client.get_devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": expected_error}

    # Recover and complete successfully
    mock_liebherr_client.get_devices.side_effect = None
    new_api_key = "new-api-key-recovered"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: new_api_key}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == new_api_key
