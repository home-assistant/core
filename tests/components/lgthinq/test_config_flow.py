"""Test the lgthinq config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    DOMAIN,
    ErrorCode,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import mock_thinq_api_response
from .const import MOCK_COUNTRY, MOCK_ENTRY_NAME, MOCK_PAT, SOURCE_REGION

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test that an thinq entry is normally created with valid values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCESS_TOKEN: MOCK_PAT,
            CONF_NAME: MOCK_ENTRY_NAME,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_REGION

    with patch("homeassistant.components.lgthinq.config_flow.ThinQApi") as mock:
        thinq_api = mock.return_value
        thinq_api.async_get_device_list = AsyncMock(
            return_value=mock_thinq_api_response(status=200, body={})
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_COUNTRY: MOCK_COUNTRY},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == MOCK_ENTRY_NAME
        assert result["data"][CONF_ACCESS_TOKEN] == MOCK_PAT
        assert result["data"][CONF_COUNTRY] == MOCK_COUNTRY

        # Since a client_id is generated randomly each time,
        # We can just check that the prefix format is correct.
        client_id: str = result["data"][CONF_CONNECT_CLIENT_ID]
        assert client_id.startswith(CLIENT_PREFIX)


async def test_config_flow_invalid_pat(hass: HomeAssistant) -> None:
    """Test that thinq flow should be aborted with an invalid PAT."""
    with patch("homeassistant.components.lgthinq.config_flow.ThinQApi") as mock:
        thinq_api = mock.return_value
        thinq_api.async_get_device_list = AsyncMock(
            return_value=mock_thinq_api_response(status=400, error_code="1218")
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_REGION},
            data={CONF_COUNTRY: MOCK_COUNTRY},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == ErrorCode.INVALID_TOKEN


async def test_config_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that thinq flow should be aborted when already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_ACCESS_TOKEN: MOCK_PAT,
            CONF_NAME: MOCK_ENTRY_NAME,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
