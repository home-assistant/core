"""Tests for the NRGkick config flow."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock

from nrgkick_api import (
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
)
import pytest

from homeassistant.components.nrgkick.api import (
    NRGkickApiClientError,
    NRGkickApiClientInvalidResponseError,
)
from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.101"),
    ip_addresses=[ip_address("192.168.1.101")],
    hostname="nrgkick.local.",
    name="NRGkick Test._nrgkick._tcp.local.",
    port=80,
    properties={
        "serial_number": "TEST123456",
        "device_name": "NRGkick Test",
        "model_type": "NRGkick Gen2",
        "json_api_enabled": "1",
        "json_api_version": "v1",
    },
    type="_nrgkick._tcp.local.",
)

ZEROCONF_DISCOVERY_INFO_DISABLED_JSON_API = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.101"),
    ip_addresses=[ip_address("192.168.1.101")],
    hostname="nrgkick.local.",
    name="NRGkick Test._nrgkick._tcp.local.",
    port=80,
    properties={
        "serial_number": "TEST123456",
        "device_name": "NRGkick Test",
        "model_type": "NRGkick Gen2",
        "json_api_enabled": "0",
        "json_api_version": "v1",
    },
    type="_nrgkick._tcp.local.",
)

ZEROCONF_DISCOVERY_INFO_NO_SERIAL = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.101"),
    ip_addresses=[ip_address("192.168.1.101")],
    hostname="nrgkick.local.",
    name="NRGkick Test._nrgkick._tcp.local.",
    port=80,
    properties={
        "device_name": "NRGkick Test",
        "model_type": "NRGkick Gen2",
        "json_api_enabled": "1",
        "json_api_version": "v1",
    },
    type="_nrgkick._tcp.local.",
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_nrgkick_api: AsyncMock) -> None:
    """Test we can set up successfully without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "TEST123456"


async def test_user_flow_with_credentials(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we can setup when authentication is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    assert result["result"].unique_id == "TEST123456"
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize("url", ["http://", ""])
async def test_form_invalid_host_input(
    hass: HomeAssistant,
    mock_nrgkick_api: AsyncMock,
    mock_setup_entry: AsyncMock,
    url: str,
) -> None:
    """Test we handle invalid host input during normalization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: url}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_fallback_title_when_device_name_missing(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock
) -> None:
    """Test we fall back to a default title when device name is missing."""
    mock_nrgkick_api.get_info.return_value = {"general": {"serial_number": "ABC"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_invalid_response_when_serial_missing(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, mock_info_data: dict[str, Any]
) -> None:
    """Test we handle invalid device info response."""
    mock_nrgkick_api.get_info.return_value = {"general": {"device_name": "NRGkick"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_response"}

    mock_nrgkick_api.get_info.return_value = mock_info_data
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickApiClientInvalidResponseError, "invalid_response"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, exception: Exception, error: str
) -> None:
    """Test errors are handled and the flow can recover to CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickAuthenticationError, "invalid_auth"),
        (NRGkickApiClientInvalidResponseError, "invalid_response"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_auth_errors(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, exception: Exception, error: str
) -> None:
    """Test errors are handled and the flow can recover to CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nrgkick_api: AsyncMock
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_auth_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nrgkick_api: AsyncMock
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_discovery(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock
) -> None:
    """Test zeroconf discovery without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.101",
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.101"}
    assert result["result"].unique_id == "TEST123456"


async def test_zeroconf_discovery_with_credentials(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test zeroconf discovery flow (auth required)."""

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["description_placeholders"] == {"device_ip": "192.168.1.101"}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {
        CONF_HOST: "192.168.1.101",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    assert result["result"].unique_id == "TEST123456"
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientInvalidResponseError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_errors(
    hass: HomeAssistant,
    mock_nrgkick_api: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test zeroconf confirm step reports errors."""
    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf discovery when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock
) -> None:
    """Test zeroconf discovery when JSON API is disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO_DISABLED_JSON_API,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.101",
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.101"}
    assert result["result"].unique_id == "TEST123456"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled_stale_mdns(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock
) -> None:
    """Test zeroconf discovery when JSON API is disabled."""
    mock_nrgkick_api.test_connection.side_effect = NRGkickAPIDisabledError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.101",
    }

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.101"}
    assert result["result"].unique_id == "TEST123456"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickApiClientInvalidResponseError, "invalid_response"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled_errors(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock, exception: Exception, error: str
) -> None:
    """Test zeroconf discovery when JSON API is disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO_DISABLED_JSON_API,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.101",
    }

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.101"}
    assert result["result"].unique_id == "TEST123456"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled_with_credentials(
    hass: HomeAssistant, mock_nrgkick_api: AsyncMock
) -> None:
    """Test JSON API disabled flow that requires authentication afterwards."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO_DISABLED_JSON_API,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.101",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickAuthenticationError, "invalid_auth"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_enable_json_api_auth_errors(
    hass: HomeAssistant, mock_nrgkick_api, exception: Exception, error: str
) -> None:
    """Test JSON API enable auth step reports errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO_DISABLED_JSON_API,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAuthenticationError, "invalid_auth"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_auth_errors(
    hass: HomeAssistant,
    mock_nrgkick_api: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test zeroconf auth step reports errors."""
    mock_nrgkick_api.test_connection.side_effect = NRGkickAuthenticationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_no_serial_number(hass: HomeAssistant) -> None:
    """Test zeroconf discovery without serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_INFO_NO_SERIAL,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    assert mock_config_entry.data[CONF_USERNAME] == "new_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_pass"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NRGkickAPIDisabledError, "json_api_disabled"),
        (NRGkickAuthenticationError, "invalid_auth"),
        (NRGkickApiClientInvalidResponseError, "invalid_response"),
        (NRGkickConnectionError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication flow error handling and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_nrgkick_api.test_connection.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test reauthentication aborts on unique ID mismatch."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_nrgkick_api.get_info.return_value = {
        "general": {"serial_number": "DIFFERENT123", "device_name": "Other"}
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
