"""Test the RainbowMiner config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from rainbowminer_api_client import RainbowMinerAuthError, RainbowMinerConnectionError

from homeassistant import config_entries
from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST, TEST_PORT, VALID_STATUS, mock_rainbowminer_endpoints

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _user_input(**overrides: str | int) -> dict[str, str | int]:
    """Return a minimal valid user input."""
    data: dict[str, str | int] = {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    data.update(overrides)
    return data


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_rainbowminer_endpoints(aioclient_mock, status=VALID_STATUS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"RainbowMiner {TEST_HOST}:{TEST_PORT}"
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}


async def test_form_with_auth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form with username and password."""
    mock_rainbowminer_endpoints(aioclient_mock, status=VALID_STATUS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _user_input(
            username="test-user",
            password="test-pass",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "test-user"
    assert result["data"][CONF_PASSWORD] == "test-pass"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rainbowminer.config_flow.RainbowMinerClient.get_status",
        side_effect=RainbowMinerAuthError("Unauthorized"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.rainbowminer.config_flow.RainbowMinerClient.get_status",
        return_value=VALID_STATUS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rainbowminer.config_flow.RainbowMinerClient.get_status",
        side_effect=RainbowMinerConnectionError("Connection refused"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.rainbowminer.config_flow.RainbowMinerClient.get_status",
        return_value=VALID_STATUS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
    )
    entry.add_to_hass(hass)

    mock_rainbowminer_endpoints(aioclient_mock, status=VALID_STATUS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
