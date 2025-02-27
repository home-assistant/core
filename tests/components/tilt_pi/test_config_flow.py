"""Test the Tilt config flow."""

from types import MappingProxyType

import aiohttp

from homeassistant import config_entries
from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST, TEST_PORT

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_async_step_user_gets_form(hass: HomeAssistant) -> None:
    """Test that we can view the form when there is no previous user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_async_step_user_creates_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry_data: MappingProxyType[str, any],
    tiltpi_api_all_response: list[dict[str, any]],
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        json=tiltpi_api_all_response,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_config_entry_data,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == mock_config_entry_data


async def test_async_step_user_returns_error_form_client_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry_data: MappingProxyType[str, any],
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_config_entry_data,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
