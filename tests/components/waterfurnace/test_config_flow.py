"""Test the WaterFurnace config flow."""

from typing import Any, cast
from unittest.mock import Mock

from waterfurnace.waterfurnace import WFCredentialError, WFException

from homeassistant import config_entries
from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test successful user flow."""
    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WaterFurnace TEST_GWID_12345"
    assert result["data"] == {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    assert result["result"].unique_id == "TEST_GWID_12345"

    # Verify login was called (once during config flow, once during setup)
    assert mock_waterfurnace_client.login.called


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test user flow with invalid credentials."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        ),
    )
    assert result["type"] is FlowResultType.FORM

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "bad_user",
                CONF_PASSWORD: "bad_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Verify we can recover from the error
    mock_waterfurnace_client.login.side_effect = None

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test user flow with connection error."""
    mock_waterfurnace_client.login.side_effect = WFException("Connection failed")  # type: ignore[attr-defined]

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        ),
    )
    assert result["type"] is FlowResultType.FORM

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_gwid(
    hass: HomeAssistant, mock_waterfurnace_client_no_gwid: Mock
) -> None:
    """Test user flow when device has no GWID."""
    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        ),
    )
    assert result["type"] is FlowResultType.FORM

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        ),
    )
    assert result["type"] is FlowResultType.FORM

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test successful import flow from YAML."""
    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WaterFurnace TEST_GWID_12345"
    assert result["data"] == {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    assert result["result"].unique_id == "TEST_GWID_12345"


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test import flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test import flow with connection error."""
    mock_waterfurnace_client.login.side_effect = WFException("Connection failed")

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_invalid_auth(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test import flow with invalid credentials."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )

    result = cast(
        dict[str, Any],
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "bad_user",
                CONF_PASSWORD: "bad_password",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
