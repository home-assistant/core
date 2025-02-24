"""Test the Tilt config flow."""

from typing import Final

import aiohttp

from homeassistant import config_entries
from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker

TEST_TILTPI_DATA: Final = {
    CONF_NAME: "Test TiltPi",
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 1880,
}


async def test_async_step_user_gets_form(hass: HomeAssistant) -> None:
    """Test that we can view the form when there is no previous user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None


async def test_async_step_user_creates_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tiltpi_api_all_response: list[dict[str, any]],
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    aioclient_mock.get(
        "http://192.168.1.100:1880/macid/all",
        json=tiltpi_api_all_response,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_TILTPI_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_TILTPI_DATA


async def test_async_step_user_returns_error_form_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    aioclient_mock.get(
        "http://192.168.1.100:1880/macid/all",
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_TILTPI_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
