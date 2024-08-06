"""Test the Nice G.O. config flow."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from nice_go import AuthFailedError
import pytest

from homeassistant.components.nice_go.const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_setup_entry: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "uuid.uuid4",
        return_value="test-uuid",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test-email",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == {
        CONF_EMAIL: "test-email",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-refresh-token",
        CONF_REFRESH_TOKEN_CREATION_TIME: freezer.time_to_freeze.timestamp(),
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "title_placeholders": {"name": mock_config_entry.title},
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "uuid.uuid4",
        return_value="test-uuid",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "new-email",
                CONF_PASSWORD: "new-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == {
        CONF_EMAIL: "new-email",
        CONF_PASSWORD: "new-password",
        CONF_REFRESH_TOKEN: "test-refresh-token",
        CONF_REFRESH_TOKEN_CREATION_TIME: freezer.time_to_freeze.timestamp(),
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [(AuthFailedError, "invalid_auth"), (Exception, "unknown")],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle invalid auth."""
    mock_nice_go.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_nice_go.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
