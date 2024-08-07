"""Test the lgthinq config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_SOUNDBAR,
    CONF_ENTRY_TYPE_THINQ,
    CONF_ENTRY_TYPE_WEBOSTV,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY,
    CONF_NAME,
    CONF_SOURCE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from tests.common import MockConfigEntry

from .common import mock_thinq_api_response
from .const import (
    SOURCE_REGION,
    SOURCE_THINQ,
    THINQ_TEST_COUNTRY,
    THINQ_TEST_NAME,
    THINQ_TEST_PAT,
)


async def test_show_menu(hass: HomeAssistant) -> None:
    """Test that the feature selection menu is shown on the first step."""
    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == SOURCE_USER
    assert result["menu_options"] == [
        CONF_ENTRY_TYPE_THINQ,
        CONF_ENTRY_TYPE_WEBOSTV,
        CONF_ENTRY_TYPE_SOUNDBAR,
    ]


async def test_thinq_flow(hass: HomeAssistant) -> None:
    """Test that an thinq entry is normally created with valid values."""
    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": SOURCE_THINQ},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_THINQ

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCESS_TOKEN: THINQ_TEST_PAT,
            CONF_NAME: THINQ_TEST_NAME,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_REGION

    with patch(
        "homeassistant.components.lgthinq.config_flow.ThinQApi"
    ) as mock:
        thinq_api = mock.return_value
        thinq_api.async_get_device_list = AsyncMock(
            return_value=mock_thinq_api_response(status=200, body={})
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_COUNTRY: THINQ_TEST_COUNTRY},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == THINQ_TEST_NAME
        assert result["data"][CONF_ACCESS_TOKEN] == THINQ_TEST_PAT
        assert result["data"][CONF_COUNTRY] == THINQ_TEST_COUNTRY
        assert result["data"][CONF_ENTRY_TYPE] == CONF_ENTRY_TYPE_THINQ

        # Since a client_id is generated randomly each time,
        # We can just check that the prefix format is correct.
        client_id: str = result["data"][CONF_CONNECT_CLIENT_ID]
        assert client_id.startswith(CLIENT_PREFIX)


async def test_thinq_flow_invalid_pat(hass: HomeAssistant) -> None:
    """Test that thinq flow should be aborted with an invalid PAT."""
    with patch(
        "homeassistant.components.lgthinq.config_flow.ThinQApi"
    ) as mock:
        thinq_api = mock.return_value
        thinq_api.async_get_device_list = AsyncMock(
            return_value=mock_thinq_api_response(status=400, error_code="1218")
        )
        result: ConfigFlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_REGION},
            data={CONF_COUNTRY: THINQ_TEST_COUNTRY},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "1218"


async def test_thinq_flow_already_configured(
    hass: HomeAssistant, config_entry_thinq: MockConfigEntry
) -> None:
    """Test that thinq flow should be aborted when already configured."""
    config_entry_thinq.add_to_hass(hass)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_THINQ},
        data={
            CONF_ACCESS_TOKEN: THINQ_TEST_PAT,
            CONF_NAME: THINQ_TEST_NAME,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
