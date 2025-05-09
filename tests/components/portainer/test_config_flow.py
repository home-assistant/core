"""Test the Portainer config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_TEST_CONFIG

from tests.common import MockConfigEntry

MOCK_USER_SETUP = {
    CONF_HOST: "https://127.0.0.1:9000/",
    CONF_API_KEY: "test_api_key",
    CONF_VERIFY_SSL: True,
}


async def test_form(
    hass: HomeAssistant,
    mock_portainer_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:9000/"
    assert result["data"] == MOCK_TEST_CONFIG


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            PortainerAuthenticationError,
            "invalid_auth",
        ),
        (
            PortainerConnectionError,
            "cannot_connect",
        ),
        (
            PortainerTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions."""
    mock_portainer_client.get_endpoints.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_portainer_client.get_endpoints.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:9000/"
    assert result["data"] == MOCK_TEST_CONFIG


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we handle duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "https://127.0.0.1:9000/",
            CONF_API_KEY: "test_api_key",
        },
        unique_id="test_api_key",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
