"""Test the LibreNMS config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError
from aiolibrenms.exceptions import LibrenmsUnauthenticatedError
import pytest

from homeassistant.components.librenms.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_step_user(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_librenms: Mock
) -> None:
    """Test a user initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "librenms"
    assert result["data"] == MOCK_CONFIG_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            LibrenmsUnauthenticatedError({"message": "Unauthenticated."}),
            "invalid_auth",
        ),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_user_error_handling(
    hass: HomeAssistant, mock_librenms: Mock, exception: Exception, error: str
) -> None:
    """Test a user initiated config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_librenms.system.async_get_system_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_librenms.system.async_get_system_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_user_invalid_url(hass: HomeAssistant, mock_librenms: Mock) -> None:
    """Test a user initiated config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MOCK_USER_DATA, CONF_URL: "hts://invalid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "invalid_url"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_already_configured(
    hass: HomeAssistant, mock_librenms: Mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
