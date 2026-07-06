"""Test the aidot config flow."""

from unittest.mock import AsyncMock, MagicMock

from aidot.exceptions import AidotUserOrPassIncorrect
from aiohttp import ClientError
import pytest

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_COUNTRY, TEST_EMAIL, TEST_LOGIN_RESP, TEST_PASSWORD

from tests.common import MockConfigEntry


async def test_config_flow_cloud_login_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful config flow using cloud login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_EMAIL} {TEST_COUNTRY}"
    assert result["data"] == TEST_LOGIN_RESP
    assert result["result"].unique_id == TEST_LOGIN_RESP["id"]


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AidotUserOrPassIncorrect, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    patch_aidot_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a failed config flow using cloud connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    patch_aidot_client.async_post_login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: "ErrorPassword",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    patch_aidot_client.async_post_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_LOGIN_RESP


async def test_form_abort_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
