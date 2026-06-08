"""Test the MELCloud Home config flow."""

from unittest.mock import AsyncMock

from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the user form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT[CONF_EMAIL]
    assert result["data"] == MOCK_USER_INPUT


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (MelCloudHomeAuthenticationError("bad creds"), "invalid_auth"),
        (MelCloudHomeConnectionError("offline"), "cannot_connect"),
        (MelCloudHomeTimeoutError("timed out"), "timeout_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all user step exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_melcloud_client.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_melcloud_client.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT[CONF_EMAIL]
    assert result["data"] == MOCK_USER_INPUT


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-uuid-1",
        data=MOCK_USER_INPUT,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
