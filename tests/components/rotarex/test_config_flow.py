# tests/components/rotarex/test_config_flow.py
"""Test the Rotarex config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from rotarex_dimes_srg_api import InvalidAuth

from homeassistant import config_entries
from homeassistant.components.rotarex.const import DOMAIN, NAME
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_rotarex_api")


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rotarex.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_form(hass: HomeAssistant, mock_rotarex_api: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test_password",
    }
    assert result2["result"].unique_id == "test@example.com"
    assert mock_rotarex_api.login.call_count >= 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidAuth, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, mock_rotarex_api: AsyncMock, exception: Exception, error: str
) -> None:
    """Test we handle errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_rotarex_api.login.side_effect = exception

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    # Verify we can recover by submitting valid credentials
    mock_rotarex_api.login.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
