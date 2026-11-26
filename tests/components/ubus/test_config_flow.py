"""Tests for the OpenWrt (ubus) config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ubus.const import CONF_DHCP_SOFTWARE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test the user flow creates an entry with the default DHCP software."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_user_flow_ssl_options(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the user flow stores the selected SSL options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**USER_INPUT, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is ssl
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
    )


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test the user flow recovers after a connection error."""
    mock_ubus.return_value.connect.side_effect = ConnectionError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_ubus.return_value.connect.side_effect = None
    mock_ubus.return_value.connect.return_value = "session-id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "connect",
    [
        pytest.param(
            {"side_effect": PermissionError("Access denied")}, id="access_denied"
        ),
        pytest.param({"side_effect": None, "return_value": None}, id="no_session"),
    ],
)
async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    connect: dict,
) -> None:
    """Test the user flow reports invalid credentials and then recovers."""
    mock_ubus.return_value.connect.configure_mock(**connect)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_ubus.return_value.connect.configure_mock(
        side_effect=None, return_value="session-id"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test importing a YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_preserves_dhcp_software(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test a non-default DHCP software choice survives the import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG, CONF_DHCP_SOFTWARE: "odhcpd"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DHCP_SOFTWARE] == "odhcpd"


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_import_flow_preserves_ssl_options(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the SSL options survive the import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is ssl
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(TypeError, "cannot_connect", id="cannot_connect"),
        pytest.param(PermissionError, "invalid_auth", id="invalid_auth"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the import flow aborts when the router can't be logged in to."""
    mock_ubus.return_value.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
