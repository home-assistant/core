"""Test the FMD config flow."""

from unittest.mock import MagicMock, patch

from fmd_api import AuthenticationError, FmdApiException
import pytest

from homeassistant import config_entries
from homeassistant.components.fmd.const import DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_ID, TEST_PASSWORD, TEST_URL

from tests.common import MockConfigEntry

USER_INPUT = {CONF_URL: TEST_URL, CONF_ID: TEST_ID, CONF_PASSWORD: TEST_PASSWORD}


async def test_form(
    hass: HomeAssistant,
    mock_fmd_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_ID
    assert result["data"][CONF_URL] == TEST_URL
    assert result["data"][CONF_ID] == TEST_ID
    assert "artifacts" in result["data"]
    assert "password" not in result["data"]


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthenticationError("nope"), "invalid_auth"),
        (FmdApiException("boom"), "cannot_connect"),
        (Exception("surprise"), "unknown"),
    ],
)
async def test_form_errors_then_success(
    hass: HomeAssistant,
    mock_fmd_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors are shown, then the flow recovers to CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fmd.config_flow.FmdClient.create",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_fmd_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
