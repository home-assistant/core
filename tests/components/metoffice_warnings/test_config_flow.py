"""Tests for Met Office Weather Warnings config flow."""

import pytest

from homeassistant.components.metoffice_warnings.const import CONF_REGION, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_REGION, TEST_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(
    hass: HomeAssistant,
    mock_warnings_response: AiohttpClientMocker,
) -> None:
    """Test the full user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REGION: TEST_REGION},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "South West England"
    assert result["data"] == {CONF_REGION: TEST_REGION}
    assert result["result"].unique_id == TEST_REGION


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_warnings_response: AiohttpClientMocker,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REGION: TEST_REGION},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we show error on connection failure."""
    aioclient_mock.get(TEST_URL, exc=TimeoutError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REGION: TEST_REGION},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
